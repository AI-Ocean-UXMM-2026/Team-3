(function (root) {
  'use strict';
  const KEY = 'lannpya.delivery.v1';
  const BASE = { lat: 16.8254, lng: 96.1309 };
  const seed = () => ({ version: 1, revision: 0, events: [], stops: [
    { id: 'LP-2048', name: 'Ma Hnin', area: 'Kamayut', cod: 18000, state: 'delivered', collected: 18000, time: '10:00–12:00' },
    { id: 'LP-2047', name: 'Ko Zaw', area: 'University Ave', cod: 0, state: 'delivered', collected: 0, time: '10:00–12:00' },
    { id: 'LP-2046', name: 'Daw Khin', area: 'Hledan', cod: 12500, state: 'delivered', collected: 12500, time: '10:00–12:00' },
    { id: 'LP-2045', name: 'Ma Thandar', area: 'Kamayut', shop: 'Thida Boutique', item: 'Floral Summer Dress', cod: 28000, state: 'queued', collected: null, time: '10:00–12:00', note: '', answer: '', confirmed: false, attempts: 0, locked: false, pin: { ...BASE }, landmark: 'အဆွေတော်နား၊ ၄ ထပ်တိုက် ညာဘက်ခန်း' },
    { id: 'LP-2044', name: 'Ko Min', area: 'Thiri Mingalar Rd', cod: 35000, state: 'queued', time: '12:00–14:00' },
    { id: 'LP-2043', name: 'Ma Su', area: 'Hledan Junction', cod: 0, state: 'queued', time: '14:00–16:00' },
    { id: 'LP-2042', name: 'U Tun', area: 'Sanchaung', cod: 22000, state: 'queued', time: '14:00–16:00' },
    { id: 'LP-2041', name: 'Ma Ei', area: 'Sanchaung', cod: 45000, state: 'queued', time: '16:00–18:00' }
  ] });
  const clone = x => JSON.parse(JSON.stringify(x));
  const distance = (a, b) => {
    const rad = d => d * Math.PI / 180;
    const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
    return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  };
  function createStore(storage, now = () => Date.now()) {
    let state;
    let persistent = true;
    try { state = JSON.parse(storage?.getItem(KEY) || 'null'); } catch { persistent = false; }
    if (!state || state.version !== 1 || !Array.isArray(state.stops) || !Array.isArray(state.events)) state = seed();
    const listeners = new Set();
    let verified = false;
    let challenge = null;
    function save() {
      try { storage?.setItem(KEY, JSON.stringify(state)); if (!storage) persistent = false; } catch { persistent = false; }
      listeners.forEach(fn => fn());
    }
    const getStop = id => state.stops.find(s => s.id === id);
    function commit(type, id, patch, text) {
      const stop = getStop(id);
      if (!stop) throw new Error('Delivery not found');
      Object.assign(stop, patch);
      state.revision++;
      state.events.unshift({ id: `${now()}-${state.revision}`, orderId: id, type, text, at: now() });
      state.events = state.events.slice(0, 100);
      save();
    }
    function editable() {
      const s = getStop('LP-2045');
      if (!verified || s.locked) throw new Error('Verify the phone check first.');
      if (['delivered', 'return'].includes(s.state)) throw new Error('This delivery can no longer be changed.');
      return s;
    }
    return {
      snapshot: () => clone(state),
      stop: id => clone(getStop(id)),
      persistent: () => persistent,
      verified: () => verified,
      otpPreview: () => challenge&&challenge.expiresAt>now()&&!getStop('LP-2045').locked?challenge.code:null,
      subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
      queue() { return clone(state.stops.filter(s => ['queued', 'retry'].includes(s.state)).sort((a,b) => a.time.localeCompare(b.time) || (a.state === 'retry') - (b.state === 'retry'))); },
      requestOtp() {
        const s=getStop('LP-2045');
        if(s.locked)throw new Error('Link locked after three incorrect attempts. Contact the shop.');
        if(challenge&&challenge.expiresAt>now()&&challenge.resendAt>now())throw new Error('Wait before requesting another code.');
        challenge={code:'123456',expiresAt:now()+300000,resendAt:now()+60000};
        state.revision++;save();
        return {mode:'DEMO',destinationMasked:'••••••••',expiresAt:challenge.expiresAt,resendAfter:challenge.resendAt,simulationOnly:true};
      },
      verify(digits) {
        const s = getStop('LP-2045');
        if (s.locked) throw new Error('Link locked after three incorrect attempts. Contact the shop.');
        if(!challenge||challenge.expiresAt<=now()){challenge=null;throw new Error('Request a fresh six-digit code first.');}
        if (!/^\d{6}$/.test(digits)) throw new Error('Enter exactly six digits.');
        if (digits !== challenge.code) {
          const attempts = s.attempts + 1;
          commit('otp_check_failed', s.id, { attempts, locked: attempts >= 3 }, attempts >= 3 ? 'Buyer link locked — shop action required' : 'Buyer OTP check failed');
          if(attempts>=3)challenge=null;
          throw new Error(attempts >= 3 ? 'Link locked. Contact the shop to request a new link.' : `Incorrect digits. ${3 - attempts} attempts remaining.`);
        }
        challenge=null;
        verified = true;
        save();
      },
      confirm({ pin, time, answer, note }) {
        const s = editable();
        if (!pin || !Number.isFinite(pin.lat) || !Number.isFinite(pin.lng) || distance(BASE, pin) > 500) throw new Error('Keep the pin inside the 500 m boundary.');
        if (!['10:00–12:00','12:00–14:00','14:00–16:00','16:00–18:00'].includes(time)) throw new Error('Choose an available delivery window.');
        if (!['At home','Leave with security'].includes(answer)) throw new Error('Choose how to receive your parcel.');
        commit('buyer_confirmed', s.id, { pin, time, answer, note: String(note || '').slice(0, 300), confirmed: true, state: 'queued' }, `Buyer confirmed ${time} · ${answer}`);
      },
      complete(id, amount) {
        const s = getStop(id);
        if (!s || !['queued','retry'].includes(s.state)) throw new Error('This stop is already closed.');
        if (!Number.isInteger(amount) || amount < 0) throw new Error('Enter a whole MMK amount of zero or more.');
        if (s.cod === 0 && amount !== 0) throw new Error('This order is prepaid. Do not collect cash.');
        commit('delivered', id, { state: 'delivered', collected: amount, deliveredAt: now(), discrepancy: amount !== s.cod }, amount === s.cod ? `Delivered · ${amount.toLocaleString()} MMK recorded` : `Delivered · COD mismatch: expected ${s.cod}, received ${amount}`);
      },
      fail(id, reason, resolution) {
        const s = getStop(id);
        if (!s || !['queued','retry'].includes(s.state)) throw new Error('This stop is already closed.');
        if (!['Buyer not answering','Not at home','Can’t find the place','Buyer refused'].includes(reason)) throw new Error('Choose a failure reason.');
        if (!['retry','return'].includes(resolution)) throw new Error('Choose retry or return.');
        commit('delivery_failed', id, { state: resolution, failureReason: reason, ...(resolution === 'retry' ? { time: '16:00–18:00' } : {}) }, `${reason} · ${resolution === 'retry' ? 'Retry at 16:00–18:00' : 'Return to hub'}`);
      },
      refresh() {
        try { const other = JSON.parse(storage?.getItem(KEY) || 'null'); if (other?.version === 1 && other.revision > state.revision) { state = other; listeners.forEach(fn => fn()); } } catch { /* retain in-memory state */ }
      }
    };
  }
  const api = { createStore, distance, BASE, KEY };
  if (typeof module !== 'undefined') module.exports = api;
  else root.DeliveryDomain = api;
})(typeof window === 'undefined' ? globalThis : window);
