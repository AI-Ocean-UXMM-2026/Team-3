"""Bounded capacitated VRPTW. Provider matrices are costs, never AI guesses."""

import time
from datetime import timedelta

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.schemas.routing import OptimizationResult, PlannedStop, PlannedVehicle


def optimize(query, matrix, stops, available_riders):
    started = time.perf_counter()
    riders = available_riders
    if not riders:
        return OptimizationResult(
            solver_status="INFEASIBLE",
            elapsed_ms=0,
            provider=matrix.provider,
            quality=matrix.quality,
            matrix_size=len(matrix.locations),
            vehicles=[],
            unassigned=[{"order_id": s["order_id"], "reason": "NO_AVAILABLE_RIDER"} for s in stops],
            warnings=matrix.warnings,
            attribution=matrix.attribution,
        )
    n, v = len(stops) + 1, len(riders)
    horizon = int((query.operating_window.end - query.operating_window.start).total_seconds())
    manager = pywrapcp.RoutingIndexManager(n, v, 0)
    routing = pywrapcp.RoutingModel(manager)
    services = [0] + [s["service_seconds"] for s in stops]
    costs = matrix.durations if query.objective == "duration" else matrix.distances

    def value(table, a, b):
        i, j = manager.IndexToNode(a), manager.IndexToNode(b)
        return 0 if j == 0 and not query.return_to_hub else table[i][j]

    def transit(a, b):
        return (value(matrix.durations, a, b) or 0) + services[manager.IndexToNode(a)]

    arc = routing.RegisterTransitCallback(lambda a, b: value(costs, a, b) or 0)
    routing.SetArcCostEvaluatorOfAllVehicles(arc)
    clock = routing.RegisterTransitCallback(transit)
    routing.AddDimension(clock, horizon, horizon, True, "Time")
    times = routing.GetDimensionOrDie("Time")
    demand = routing.RegisterUnaryTransitCallback(
        lambda i: 0 if manager.IndexToNode(i) == 0 else stops[manager.IndexToNode(i) - 1]["demand"]
    )
    routing.AddDimensionWithVehicleCapacity(demand, 0, [r.capacity for r in riders], True, "Load")
    explanations = {}
    for k, stop in enumerate(stops, 1):
        index = manager.NodeToIndex(k)
        routing.AddDisjunction([index], 1000000000000)
        lo, hi = 0, horizon - services[k]
        if stop.get("window"):
            window = stop["window"]
            lo = max(0, int((window.start - query.operating_window.start).total_seconds()))
            hi = min(
                hi, int((window.end - query.operating_window.start).total_seconds()) - services[k]
            )
        fixed = stop.get("rider_id")
        if fixed:
            allowed = [i for i, rider in enumerate(riders) if str(rider.rider_id) == fixed]
            if allowed:
                # OR-Tools 9.15's Windows Span wrapper rejects Python lists here.
                # Restrict the existing IntVar domain instead; retain -1 for dropped stops.
                for vehicle in range(v):
                    if vehicle not in allowed:
                        routing.VehicleVar(index).RemoveValue(vehicle)
            else:
                explanations[k] = "ASSIGNED_RIDER_UNAVAILABLE_OR_NOT_SELECTED"
        if lo > hi:
            explanations[k] = "TIME_WINDOW_OUTSIDE_HORIZON_OR_SERVICE_TOO_LONG"
        if stop["demand"] > max(r.capacity for r in riders):
            explanations[k] = "PARCEL_DEMAND_EXCEEDS_ALL_CAPACITIES"
        if k in explanations:
            routing.ActiveVar(index).SetValue(0)
        else:
            times.CumulVar(index).SetRange(lo, hi)
    # Null costs are unreachable, never zero-cost roads. Remove every corresponding arc.
    for i in range(routing.Size()):
        for j in range(routing.Size()):
            if i != j and value(matrix.durations, i, j) is None:
                routing.NextVar(i).RemoveValue(j)
        for vehicle in range(v):
            end = routing.End(vehicle)
            if value(matrix.durations, i, end) is None:
                routing.NextVar(i).RemoveValue(end)
    for vehicle in range(v):
        routing.AddVariableMinimizedByFinalizer(times.CumulVar(routing.End(vehicle)))
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search.time_limit.seconds = query.solver_seconds
    search.sat_parameters.num_search_workers = 1
    solution = routing.SolveWithParameters(search)
    vehicles, served = [], set()
    if solution:
        for vehicle, rider in enumerate(riders):
            index, previous, distance, travel, output = routing.Start(vehicle), 0, 0, 0, []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node:
                    stop = stops[node - 1]
                    served.add(node)
                    distance += matrix.distances[previous][node]
                    travel += matrix.durations[previous][node]
                    arrival = query.operating_window.start + timedelta(
                        seconds=solution.Value(times.CumulVar(index))
                    )
                    output.append(
                        PlannedStop(
                            order_id=stop["order_id"],
                            sequence=len(output) + 1,
                            arrival=arrival,
                            departure=arrival + timedelta(seconds=services[node]),
                            demand=stop["demand"],
                            latitude=matrix.locations[node].latitude,
                            longitude=matrix.locations[node].longitude,
                        )
                    )
                    previous = node
                index = solution.Value(routing.NextVar(index))
            if output:
                if query.return_to_hub:
                    distance += matrix.distances[previous][0]
                    travel += matrix.durations[previous][0]
                vehicles.append(
                    PlannedVehicle(
                        rider_id=rider.rider_id,
                        stops=output,
                        distance_meters=distance,
                        travel_seconds=travel,
                        duration_seconds=solution.Value(times.CumulVar(index)),
                    )
                )
    unassigned = [
        {
            "order_id": s["order_id"],
            "reason": explanations.get(k, "CAPACITY_TIME_WINDOW_UNREACHABLE_OR_SEARCH_LIMIT"),
        }
        for k, s in enumerate(stops, 1)
        if k not in served
    ]
    status = "FEASIBLE" if not unassigned else "PARTIAL" if served else "INFEASIBLE"
    if not solution and routing.status() == 4:
        status = "TIME_LIMIT"
    return OptimizationResult(
        solver_status=status,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
        provider=matrix.provider,
        quality=matrix.quality,
        matrix_size=n,
        vehicles=vehicles,
        unassigned=unassigned,
        attribution=matrix.attribution,
        warnings=[
            *matrix.warnings,
            "Bounded heuristic solution; global optimality is not guaranteed.",
        ],
    )
