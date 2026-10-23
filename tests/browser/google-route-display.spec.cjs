// Real Chromium, local scripts, synthetic geometry; Google SDK is stubbed, never downloaded.
const {test, expect} = require('@playwright/test');
const path = require('node:path');
const geometry = {type:'LineString',coordinates:[[96.13,16.825],[96.128,16.819],[96.125,16.815]]};

test.beforeEach(async ({page}) => {
  await page.route('**/*', route => route.abort());
  await page.setContent('<div id="map" style="width:600px;height:400px"></div>');
});

test('Google route is withheld when an approved Google map is unavailable', async ({page}) => {
  await page.addScriptTag({path:path.resolve('frontend/js/customer-map.js')});
  await page.evaluate(g => LannPyaCustomerMap.routeView(document.querySelector('#map'),g,'google'),geometry);
  await expect(page.locator('#map')).toContainText('Route geometry is withheld');
  await expect(page.locator('.leaflet-container')).toHaveCount(0);
  expect(await page.locator('script[src*="maps.googleapis.com"]').count()).toBe(0);
});

test('Google display contract converts GeoJSON longitude latitude without changing coordinates', async ({page}) => {
  await page.evaluate(() => {
    globalThis.LANNPYA_MAPS={googleKey:'synthetic-public-test-placeholder'};
    globalThis.rendered={};
    globalThis.google={maps:{
      Map:class {constructor(node,options){rendered.center=options.center;} fitBounds(){}},
      Polyline:class {constructor(options){rendered.path=options.path;} setMap(){}},
      Marker:class {constructor(options){(rendered.pins??=[]).push(options);} setMap(){}},
      LatLngBounds:class {extend(p){(rendered.bounds??=[]).push(p);}},event:{clearInstanceListeners(){}},
    }};
  });
  await page.addScriptTag({path:path.resolve('frontend/js/customer-map.js')});
  await page.evaluate(g => LannPyaCustomerMap.routeView(document.querySelector('#map'),g,'google',[{sequence:1,latitude:16.9,longitude:96.2}]),geometry);
  expect(await page.evaluate(() => rendered.path)).toEqual(geometry.coordinates.map(([lng,lat])=>({lat,lng})));
  expect(await page.evaluate(() => rendered.center)).toEqual({lat:16.825,lng:96.13});
  expect(await page.evaluate(() => rendered.pins.map(p=>p.title))).toEqual(['Road route start','Road route end','Approved stop 1; geospatial accuracy unverified']);
  expect(await page.evaluate(() => rendered.bounds)).toContainEqual({lat:16.9,lng:96.2});
  await expect(page.locator('.leaflet-container')).toHaveCount(0);
});

test('empty coordinate attributes never become a fabricated zero-zero delivery pin', async ({page}) => {
  await page.setContent('<div data-view-map data-lat="" data-lng=""></div>');
  await page.evaluate(()=>{globalThis.L={map:()=>{throw Error('Empty pin must not create a map');}};});
  await page.addScriptTag({path:path.resolve('frontend/js/customer-map.js')});
  await page.evaluate(()=>LannPyaCustomerMap.mount());
  await expect(page.locator('.leaflet-container')).toHaveCount(0);
});

test('Leaflet continues rendering explicitly synthetic offline route geometry locally', async ({page}) => {
  await page.addScriptTag({path:path.resolve('node_modules/leaflet/dist/leaflet.js')});
  await page.addScriptTag({path:path.resolve('frontend/js/customer-map.js')});
  await page.evaluate(g => LannPyaCustomerMap.routeView(document.querySelector('#map'),g,'offline'),geometry);
  await expect(page.locator('.leaflet-container')).toHaveCount(1);
  await expect(page.locator('.leaflet-tile-pane')).toHaveCount(1);
  await page.evaluate(() => LannPyaCustomerMap.destroy());
  // Leaflet retains its container CSS class on remove(); layers and controls are removed.
  await expect(page.locator('.leaflet-map-pane')).toHaveCount(0);
});
