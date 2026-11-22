(() => {
  let latestSample = null;
  let sampleTimer = null;
  let sending = false;
  let pendingSample = Promise.resolve();

  async function post(path, body) {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'The sensor request failed.');
    }
    return result;
  }

  async function reportError(error) {
    const message = error instanceof Error ? error.message : String(error);
    try {
      await post('/api/sensor/error', { message });
    } catch (reportingError) {
      console.error('Could not report sensor error:', reportingError);
    }
  }

  function onMotion(event) {
    const linearAcceleration = event.acceleration;
    const hasLinearAcceleration = linearAcceleration
      && Number.isFinite(linearAcceleration.x)
      && Number.isFinite(linearAcceleration.y)
      && Number.isFinite(linearAcceleration.z);
    const acceleration = hasLinearAcceleration
      ? linearAcceleration
      : event.accelerationIncludingGravity || {};
    const rotation = event.rotationRate || {};
    latestSample = {
      x: Number.isFinite(acceleration.x) ? acceleration.x : 0,
      y: Number.isFinite(acceleration.y) ? acceleration.y : 0,
      z: Number.isFinite(acceleration.z) ? acceleration.z : 0,
      includes_gravity: !hasLinearAcceleration,
      alpha: rotation.alpha || 0,
      beta: rotation.beta || 0,
      gamma: rotation.gamma || 0,
    };
  }

  async function sendLatestSample() {
    if (!latestSample || sending) return;
    sending = true;
    const sample = latestSample;
    latestSample = null;
    pendingSample = post('/api/sensor/sample', sample)
      .catch(reportError)
      .finally(() => { sending = false; });
    await pendingSample;
  }

  async function start() {
    try {
      if (!('DeviceMotionEvent' in window)) {
        throw new Error('This browser does not provide device motion sensors.');
      }
      if (typeof DeviceMotionEvent.requestPermission === 'function') {
        const permission = await DeviceMotionEvent.requestPermission();
        if (permission !== 'granted') {
          throw new Error('Motion sensor permission was not granted.');
        }
      }
      await post('/api/sensor/start', {});
      latestSample = null;
      window.addEventListener('devicemotion', onMotion);
      sampleTimer = window.setInterval(sendLatestSample, 120);
    } catch (error) {
      await reportError(error);
    }
  }

  async function stop() {
    if (sampleTimer !== null) {
      window.clearInterval(sampleTimer);
      sampleTimer = null;
    }
    window.removeEventListener('devicemotion', onMotion);
    await pendingSample;
    await post('/api/sensor/stop', {});
  }

  window.MoveSenseSensors = { start, stop };
  document.addEventListener('click', event => {
    if (event.target instanceof Element && event.target.closest('#movesense-start')) {
      void start();
    }
  });
})();
