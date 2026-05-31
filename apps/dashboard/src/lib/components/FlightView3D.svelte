<script lang="ts">
  import { onMount } from 'svelte';
  import * as THREE from 'three';
  import type { TelemetryFrame } from '$lib/stores/telemetry';
  import { ftToM, hasGeoFix, latLonToEnuM } from '$lib/geo';

  let {
    history = [],
    frame = null,
    heading = 0,
    altFt = 0,
    iasKt = 0,
    pitchDeg = 0,
    rollDeg = 0,
    failures = [],
    environment = null
  }: {
    history?: TelemetryFrame[];
    frame?: TelemetryFrame | null;
    heading?: number;
    altFt?: number;
    iasKt?: number;
    pitchDeg?: number;
    rollDeg?: number;
    failures?: string[];
    environment?: TelemetryFrame['environment'] | null;
  } = $props();

  let container: HTMLDivElement | undefined = $state();

  let scene: THREE.Scene;
  let camera: THREE.PerspectiveCamera;
  let renderer: THREE.WebGLRenderer;
  let aircraft: THREE.Group;
  let propeller: THREE.Group | undefined;
  let trailLine: THREE.Line;
  let cloudDeck: THREE.Mesh;
  let sunLight: THREE.DirectionalLight;
  let ground: THREE.Mesh;
  let skyDome: THREE.Mesh;
  let rafId = 0;
  let spinRate = 18;

  const renderPos = new THREE.Vector3();
  const renderQuat = new THREE.Quaternion();
  const targetInterpPos = new THREE.Vector3();
  const prevQuat = new THREE.Quaternion();
  const curQuat = new THREE.Quaternion();
  const targetInterpQuat = new THREE.Quaternion();
  const prevPoint = new THREE.Vector3();
  const curPoint = new THREE.Vector3();
  const smoothCamPos = new THREE.Vector3();
  const smoothLookAt = new THREE.Vector3();
  const euler = new THREE.Euler(0, 0, 0, 'YXZ');
  const yawOnly = new THREE.Quaternion();
  const camOffset = new THREE.Vector3();
  const lookPoint = new THREE.Vector3();
  const desiredCamPos = new THREE.Vector3();
  const trailPts: THREE.Vector3[] = [];
  let lastGoodPoint: THREE.Vector3 | null = null;

  let sessionId: string | null = null;
  let geoOrigin: { lat: number; lon: number } | null = null;
  let drEastM = 0;
  let drNorthM = 0;
  let drSimTimeS = -1;
  let lastIngestedTimestampNs = -1;
  let lastSimTimeS = -1;
  let prevKeyframe: TelemetryFrame | null = null;
  let curKeyframe: TelemetryFrame | null = null;
  let keyframeWallMs = 0;
  let renderHeadingDeg = 0;
  let renderPitchDeg = 0;
  let renderRollDeg = 0;
  let prevHeadingDeg = 0;
  let prevPitchDeg = 0;
  let prevRollDeg = 0;
  let curHeadingDeg = 0;
  let curPitchDeg = 0;
  let curRollDeg = 0;
  let pathReady = false;
  let lastFrameHeadingDeg: number | null = null;
  let targetVisSm = 10;
  let targetCeilFt = 10000;
  let smoothVisSm = 10;
  let smoothCeilFt = 10000;
  let targetAltM = 0;
  let keyframeBlendS = 0.05;
  let targetEnv: TelemetryFrame['environment'] | null | undefined = null;

  const CHASE_BACK_M = 140;
  const CHASE_RIGHT_M = 28;
  const CHASE_UP_M = 24;
  const LOOK_AHEAD_M = 60;
  const MAX_TRAIL_PTS = 900;
  const KT_TO_MS = 0.514444;
  const MAX_BLEND_S = 0.22;
  const MAX_JUMP_SCALE = 3.5;
  const extrapVel = new THREE.Vector3();

  function headingDeltaDeg(from: number, to: number): number {
    return ((to - from + 540) % 360) - 180;
  }

  function lerpHeadingDeg(a: number, b: number, t: number): number {
    return (a + headingDeltaDeg(a, b) * t + 360) % 360;
  }

  function headingToYawRad(hdgDeg: number): number {
    return Math.PI - THREE.MathUtils.degToRad(hdgDeg);
  }

  function attitudeToQuat(hdg: number, pitch: number, roll: number, out: THREE.Quaternion) {
    euler.set(
      THREE.MathUtils.degToRad(pitch),
      headingToYawRad(hdg),
      THREE.MathUtils.degToRad(roll)
    );
    out.setFromEuler(euler);
  }

  function resetFlightPath(clearTrail = true) {
    drEastM = 0;
    drNorthM = 0;
    drSimTimeS = -1;
    lastIngestedTimestampNs = -1;
    lastSimTimeS = -1;
    lastGoodPoint = null;
    prevKeyframe = null;
    curKeyframe = null;
    pathReady = false;
    lastFrameHeadingDeg = null;
    if (clearTrail) {
      trailPts.length = 0;
      updateTrailGeometry();
    }
  }

  function resetSession(session: string) {
    sessionId = session;
    geoOrigin = null;
    lastGoodPoint = null;
    resetFlightPath(true);
  }

  function snapToFrame(f: TelemetryFrame, pt: THREE.Vector3) {
    prevPoint.copy(pt);
    curPoint.copy(pt);
    renderPos.copy(pt);
    targetInterpPos.copy(pt);
    prevHeadingDeg = f.heading_deg;
    prevPitchDeg = f.pitch_deg ?? pitchDeg;
    prevRollDeg = f.roll_deg ?? rollDeg;
    curHeadingDeg = prevHeadingDeg;
    curPitchDeg = prevPitchDeg;
    curRollDeg = prevRollDeg;
    attitudeToQuat(prevHeadingDeg, prevPitchDeg, prevRollDeg, prevQuat);
    curQuat.copy(prevQuat);
    renderQuat.copy(prevQuat);
    targetInterpQuat.copy(prevQuat);
    prevKeyframe = f;
    curKeyframe = f;
    pathReady = true;
    keyframeWallMs = performance.now();
    keyframeBlendS = 0.05;
    lastGoodPoint = pt.clone();

    yawOnly.setFromAxisAngle(new THREE.Vector3(0, 1, 0), headingToYawRad(curHeadingDeg));
    camOffset.set(CHASE_RIGHT_M, CHASE_UP_M, CHASE_BACK_M).applyQuaternion(yawOnly);
    smoothCamPos.copy(pt).add(camOffset);
    lookPoint.set(0, 4, -LOOK_AHEAD_M).applyQuaternion(yawOnly).add(pt);
    smoothLookAt.copy(lookPoint);
  }

  function simTimeRewound(prev: TelemetryFrame | null, next: TelemetryFrame): boolean {
    if (!prev) return false;
    return next.sim_time_s + 2.0 < prev.sim_time_s && next.sim_time_s < 3 && prev.sim_time_s > 60;
  }

  function integrateDeadReckoning(f: TelemetryFrame) {
    if (drSimTimeS >= 0 && f.sim_time_s > drSimTimeS) {
      const dt = f.sim_time_s - drSimTimeS;
      const speedMs = f.ias_kt * KT_TO_MS;
      const hdgStart = lastFrameHeadingDeg ?? f.heading_deg;
      const hdgMid = lerpHeadingDeg(hdgStart, f.heading_deg, 0.5);
      const hdgRad = (hdgMid * Math.PI) / 180;
      drNorthM += Math.cos(hdgRad) * speedMs * dt;
      drEastM += Math.sin(hdgRad) * speedMs * dt;
    }
    lastFrameHeadingDeg = f.heading_deg;
    drSimTimeS = f.sim_time_s;
  }

  function pointFromFrame(f: TelemetryFrame): THREE.Vector3 {
    const altM = ftToM(f.alt_ft);

    if (hasGeoFix(f.lat_deg, f.lon_deg)) {
      if (!geoOrigin) {
        geoOrigin = { lat: f.lat_deg!, lon: f.lon_deg! };
      }
      const { east, north } = latLonToEnuM(f.lat_deg!, f.lon_deg!, geoOrigin.lat, geoOrigin.lon);
      const pt = new THREE.Vector3(east, altM, north);
      lastGoodPoint = pt;
      return pt;
    }

    const x = f.position?.x_m ?? 0;
    const y = f.position?.y_m ?? 0;
    if (Math.abs(x) > 1 || Math.abs(y) > 1) {
      const pt = new THREE.Vector3(x, altM, -y);
      lastGoodPoint = pt;
      return pt;
    }

    if (lastGoodPoint) {
      return new THREE.Vector3(lastGoodPoint.x, altM, lastGoodPoint.z);
    }

    return new THREE.Vector3(drEastM, altM, drNorthM);
  }

  function appendTrailPoint(pt: THREE.Vector3) {
    const last = trailPts[trailPts.length - 1];
    if (last && last.distanceToSquared(pt) < 4) return;
    trailPts.push(pt.clone());
    if (trailPts.length > MAX_TRAIL_PTS) {
      trailPts.splice(0, trailPts.length - MAX_TRAIL_PTS);
    }
  }

  function updateTrailGeometry() {
    if (!trailLine) return;
    if (trailPts.length < 2) {
      trailLine.geometry.setDrawRange(0, 0);
      return;
    }

    let attr = trailLine.geometry.getAttribute('position') as THREE.BufferAttribute | undefined;
    if (!attr || attr.count < trailPts.length) {
      const cap = Math.max(trailPts.length, 64);
      trailLine.geometry.setAttribute(
        'position',
        new THREE.BufferAttribute(new Float32Array(cap * 3), 3)
      );
      attr = trailLine.geometry.getAttribute('position') as THREE.BufferAttribute;
    }

    for (let i = 0; i < trailPts.length; i++) {
      attr.setXYZ(i, trailPts[i].x, trailPts[i].y, trailPts[i].z);
    }
    attr.needsUpdate = true;
    trailLine.geometry.setDrawRange(0, trailPts.length);
    trailLine.geometry.computeBoundingSphere();
  }

  function pushKeyframe(f: TelemetryFrame, pt: THREE.Vector3) {
    if (!pathReady) {
      snapToFrame(f, pt);
      return;
    }

    if (simTimeRewound(curKeyframe, f)) {
      trailPts.length = 0;
      drEastM = 0;
      drNorthM = 0;
      drSimTimeS = -1;
      lastFrameHeadingDeg = null;
      snapToFrame(f, pt);
      appendTrailPoint(pt);
      return;
    }

    prevKeyframe = curKeyframe;
    curKeyframe = f;
    prevPoint.copy(curPoint);
    curPoint.copy(pt);
    prevHeadingDeg = curHeadingDeg;
    prevPitchDeg = curPitchDeg;
    prevRollDeg = curRollDeg;
    curHeadingDeg = f.heading_deg;
    curPitchDeg = f.pitch_deg ?? pitchDeg;
    curRollDeg = f.roll_deg ?? rollDeg;
    attitudeToQuat(prevHeadingDeg, prevPitchDeg, prevRollDeg, prevQuat);
    attitudeToQuat(curHeadingDeg, curPitchDeg, curRollDeg, curQuat);

    const posJump = prevPoint.distanceTo(curPoint);
    const attJump = Math.max(
      Math.abs(headingDeltaDeg(prevHeadingDeg, curHeadingDeg)),
      Math.abs(curPitchDeg - prevPitchDeg),
      Math.abs(curRollDeg - prevRollDeg)
    );
    let simSpan = 0.05;
    if (prevKeyframe && curKeyframe && curKeyframe.sim_time_s > prevKeyframe.sim_time_s) {
      simSpan = Math.max(0.02, curKeyframe.sim_time_s - prevKeyframe.sim_time_s);
    }
    const jumpScale = Math.min(
      MAX_JUMP_SCALE,
      Math.max(1, posJump / 10, attJump / 5)
    );
    keyframeBlendS = Math.min(MAX_BLEND_S, simSpan * jumpScale * 2.8);
    keyframeWallMs = performance.now();
  }

  function frameTimestampNs(f: TelemetryFrame, fallbackIdx: number): number {
    if (f.timestamp_ns != null && Number.isFinite(f.timestamp_ns)) {
      return f.timestamp_ns;
    }
    return Math.floor(f.sim_time_s * 1_000_000_000) + fallbackIdx;
  }

  function ingestFrame(f: TelemetryFrame) {
    integrateDeadReckoning(f);
    const pt = pointFromFrame(f);
    pushKeyframe(f, pt);
    appendTrailPoint(pt);
  }

  function ingestNewFrames(hist: TelemetryFrame[]) {
    for (let i = 0; i < hist.length; i++) {
      const f = hist[i];
      const ts = frameTimestampNs(f, i);
      if (ts <= lastIngestedTimestampNs) continue;
      ingestFrame(f);
      lastIngestedTimestampNs = ts;
    }
  }

  function syncTelemetry(hist: TelemetryFrame[], current: TelemetryFrame | null) {
    const latest = current ?? hist[hist.length - 1];
    if (!latest) return;

    if (sessionId !== null && latest.session_id !== sessionId) {
      resetSession(latest.session_id);
    } else if (sessionId === null) {
      sessionId = latest.session_id;
    }

    ingestNewFrames(hist);

    if (latest.sim_time_s + 0.25 >= lastSimTimeS) {
      lastSimTimeS = latest.sim_time_s;
    }

    updateTrailGeometry();

    targetEnv = latest.environment ?? environment;
    targetAltM = ftToM(latest.alt_ft);
    spinRate = 12 + latest.ias_kt * 0.25;
  }

  function sampleRenderState(dt: number) {
    if (!curKeyframe || !pathReady) return;

    const wallSpan = (performance.now() - keyframeWallMs) / 1000;
    const alpha = keyframeBlendS > 0 ? Math.min(1, wallSpan / keyframeBlendS) : 1;

    targetInterpPos.lerpVectors(prevPoint, curPoint, alpha);
    targetInterpQuat.copy(prevQuat).slerp(curQuat, alpha);

    // Between telemetry frames, keep moving at last known speed/heading
    if (alpha >= 1 && curKeyframe) {
      const overS = Math.min(0.35, wallSpan - keyframeBlendS);
      if (overS > 0) {
        const speedMs = curKeyframe.ias_kt * KT_TO_MS;
        const hdgRad = (curHeadingDeg * Math.PI) / 180;
        extrapVel.set(Math.sin(hdgRad) * speedMs * overS, 0, Math.cos(hdgRad) * speedMs * overS);
        targetInterpPos.copy(curPoint).add(extrapVel);
      }
    }

    const follow = 1 - Math.exp(-dt * 16);
    renderPos.lerp(targetInterpPos, follow);
    renderQuat.slerp(targetInterpQuat, follow);

    renderHeadingDeg = lerpHeadingDeg(prevHeadingDeg, curHeadingDeg, alpha);
    renderPitchDeg = prevPitchDeg + (curPitchDeg - prevPitchDeg) * alpha;
    renderRollDeg = prevRollDeg + (curRollDeg - prevRollDeg) * alpha;
  }

  function animateFrame(dt: number) {
    if (!aircraft || !camera) return;

    sampleRenderState(dt);

    aircraft.position.copy(renderPos);
    aircraft.quaternion.copy(renderQuat);
    aircraft.updateMatrixWorld(true);

    if (ground) ground.position.set(renderPos.x, 0, renderPos.z);
    if (skyDome) skyDome.position.set(renderPos.x, renderPos.y, renderPos.z);
    if (sunLight) sunLight.position.set(renderPos.x + 140, renderPos.y + 220, renderPos.z + 90);

    const camAlpha = 1 - Math.exp(-dt * 5);
    yawOnly.setFromAxisAngle(new THREE.Vector3(0, 1, 0), headingToYawRad(renderHeadingDeg));
    camOffset.set(CHASE_RIGHT_M, CHASE_UP_M, CHASE_BACK_M).applyQuaternion(yawOnly);
    lookPoint.set(0, 4, -LOOK_AHEAD_M).applyQuaternion(yawOnly).add(renderPos);

    smoothCamPos.lerp(desiredCamPos.copy(renderPos).add(camOffset), camAlpha);
    smoothLookAt.lerp(lookPoint, camAlpha);
    camera.position.copy(smoothCamPos);
    camera.lookAt(smoothLookAt);

    tickEnvironmentFx(dt);
  }

  function tickEnvironmentFx(dt: number) {
    if (!scene || !cloudDeck) return;

    const env = targetEnv;
    targetVisSm = env?.visibility_sm ?? 10;
    targetCeilFt = env?.ceiling_ft ?? 10000;

    const envEase = 1 - Math.exp(-dt * 1.1);
    smoothVisSm += (targetVisSm - smoothVisSm) * envEase;
    smoothCeilFt += (targetCeilFt - smoothCeilFt) * envEase;

    const fogNear = Math.max(200, smoothVisSm * 200);
    const fogFar = Math.max(800, smoothVisSm * 600);
    if (scene.fog instanceof THREE.Fog) {
      scene.fog.near += (fogNear - scene.fog.near) * envEase;
      scene.fog.far += (fogFar - scene.fog.far) * envEase;
    } else {
      scene.fog = new THREE.Fog(0x9ec5e8, fogNear, fogFar);
    }

    const ceilM = ftToM(smoothCeilFt);
    const aboveClouds = targetAltM > ceilM + 80;
    cloudDeck.visible = !aboveClouds;
    cloudDeck.position.y += (ceilM - cloudDeck.position.y) * envEase;
    if (!aboveClouds) {
      const mat = cloudDeck.material as THREE.MeshStandardMaterial;
      mat.opacity += (0.45 - mat.opacity) * envEase;
    }
  }

  function groundTexture(): THREE.CanvasTexture {
    const size = 512;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#3d6b45';
    ctx.fillRect(0, 0, size, size);
    for (let i = 0; i < 9000; i++) {
      const x = Math.random() * size;
      const y = Math.random() * size;
      const g = 55 + Math.random() * 45;
      ctx.fillStyle = `rgb(${g - 18}, ${g + 8}, ${g - 28})`;
      ctx.fillRect(x, y, 2, 2);
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(80, 80);
    return tex;
  }

  function buildSkyDome(): THREE.Mesh {
    const geo = new THREE.SphereGeometry(4000, 32, 16);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: {
        topColor: { value: new THREE.Color(0x1e4d8b) },
        midColor: { value: new THREE.Color(0x5b9bd5) },
        bottomColor: { value: new THREE.Color(0xb8d9f5) }
      },
      vertexShader: `
        varying float vY;
        void main() {
          vY = normalize(position).y;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 topColor;
        uniform vec3 midColor;
        uniform vec3 bottomColor;
        varying float vY;
        void main() {
          float t = clamp(vY * 0.5 + 0.5, 0.0, 1.0);
          vec3 col = mix(bottomColor, midColor, smoothstep(0.0, 0.45, t));
          col = mix(col, topColor, smoothstep(0.45, 1.0, t));
          gl_FragColor = vec4(col, 1.0);
        }
      `
    });
    return new THREE.Mesh(geo, mat);
  }

  function buildAircraft(): THREE.Group {
    const root = new THREE.Group();
    const silver = new THREE.MeshStandardMaterial({ color: 0xc8ccd4, metalness: 0.72, roughness: 0.28 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x1f2937, metalness: 0.55, roughness: 0.4 });
    const yellow = new THREE.MeshStandardMaterial({ color: 0xf5c542, metalness: 0.35, roughness: 0.45 });
    const glass = new THREE.MeshPhysicalMaterial({
      color: 0x9ca3af,
      metalness: 0.1,
      roughness: 0.05,
      transmission: 0.55,
      transparent: true,
      opacity: 0.85
    });

    const fuse = new THREE.Mesh(new THREE.CapsuleGeometry(0.55, 5.2, 6, 12), silver);
    fuse.rotation.x = Math.PI / 2;
    fuse.position.set(0, 0.45, 0.2);
    root.add(fuse);

    const cowl = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.72, 1.1, 16), dark);
    cowl.rotation.x = Math.PI / 2;
    cowl.position.set(0, 0.48, -3.35);
    root.add(cowl);

    const canopy = new THREE.Mesh(new THREE.SphereGeometry(0.52, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2), glass);
    canopy.rotation.x = -Math.PI / 2;
    canopy.scale.set(1, 1, 1.55);
    canopy.position.set(0, 0.92, -0.55);
    root.add(canopy);

    const wing = new THREE.Mesh(new THREE.BoxGeometry(11.5, 0.14, 1.35), silver);
    wing.position.set(0, 0.38, 0.15);
    root.add(wing);

    const tipL = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.15, 1.35), yellow);
    tipL.position.set(-5.8, 0.38, 0.15);
    root.add(tipL);
    const tipR = tipL.clone();
    tipR.position.x = 5.8;
    root.add(tipR);

    const hstab = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.1, 1.0), silver);
    hstab.position.set(0, 0.52, 2.85);
    root.add(hstab);

    const vstab = new THREE.Mesh(new THREE.BoxGeometry(0.12, 1.35, 1.05), silver);
    vstab.position.set(0, 1.05, 2.85);
    root.add(vstab);

    const rudder = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.85, 0.55), yellow);
    rudder.position.set(0, 1.35, 3.25);
    root.add(rudder);

    const prop = new THREE.Group();
    prop.position.set(0, 0.48, -3.85);
    const bladeGeo = new THREE.BoxGeometry(0.08, 1.6, 0.05);
    for (let i = 0; i < 3; i++) {
      const blade = new THREE.Mesh(bladeGeo, dark);
      blade.rotation.z = (i * Math.PI * 2) / 3;
      prop.add(blade);
    }
    root.add(prop);
    propeller = prop;

    root.scale.setScalar(1.2);
    return root;
  }

  onMount(() => {
    if (!container) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x8ec4ea);
    scene.fog = new THREE.Fog(0x9ec5e8, 200, 4000);

    camera = new THREE.PerspectiveCamera(52, 1, 2.0, 12000);

    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    container.appendChild(renderer.domElement);

    skyDome = buildSkyDome();
    scene.add(skyDome);

    const hemi = new THREE.HemisphereLight(0xdceeff, 0x3d5c3a, 0.55);
    scene.add(hemi);

    sunLight = new THREE.DirectionalLight(0xfff5e6, 1.35);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.set(1024, 1024);
    scene.add(sunLight);

    ground = new THREE.Mesh(
      new THREE.PlaneGeometry(8000, 8000),
      new THREE.MeshStandardMaterial({ map: groundTexture(), roughness: 0.94, metalness: 0.02 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    cloudDeck = new THREE.Mesh(
      new THREE.PlaneGeometry(6000, 6000),
      new THREE.MeshStandardMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.4,
        depthWrite: false,
        roughness: 1,
        metalness: 0
      })
    );
    cloudDeck.rotation.x = -Math.PI / 2;
    scene.add(cloudDeck);

    aircraft = buildAircraft();
    aircraft.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });
    scene.add(aircraft);

    const trailMat = new THREE.LineBasicMaterial({ color: 0x60a5fa, transparent: true, opacity: 0.35 });
    trailLine = new THREE.Line(new THREE.BufferGeometry(), trailMat);
    scene.add(trailLine);

    const resize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w === 0 || h === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };

    const ro = new ResizeObserver(resize);
    ro.observe(container);
    resize();

    if (history.length > 0) {
      sessionId = history[0].session_id;
      ingestNewFrames(history);
      lastSimTimeS = history[history.length - 1].sim_time_s;
      updateTrailGeometry();
    }

    let last = performance.now();
    const tick = (now: number) => {
      rafId = requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (propeller) propeller.rotation.z += dt * spinRate;
      animateFrame(dt);
      renderer.render(scene, camera);
    };
    rafId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      trailLine.geometry.dispose();
      renderer.dispose();
      container?.removeChild(renderer.domElement);
    };
  });

  $effect(() => {
    syncTelemetry(history, frame);
  });
</script>

<div class="wrap">
  <div class="viewport" bind:this={container} role="img" aria-label="3D chase view synced to simulator telemetry"></div>

  <div class="hud">
    <div><span class="k">HDG</span> {heading.toFixed(0)}°</div>
    <div><span class="k">ALT</span> {altFt.toFixed(0)} ft</div>
    <div><span class="k">IAS</span> {iasKt.toFixed(0)} kt</div>
    <div><span class="k">P/R</span> {pitchDeg.toFixed(0)}° / {rollDeg.toFixed(0)}°</div>
  </div>

  {#if failures.length}
    <div class="tags">
      {#each failures as f}
        <span>{f.replace(/_/g, ' ')}</span>
      {/each}
    </div>
  {/if}

  <div class="badge-3d">Chase cam · telemetry</div>
</div>

<style>
  .wrap {
    position: relative;
    flex: 1;
    min-height: 160px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    overflow: hidden;
    background: #1a3a5c;
  }

  .viewport {
    width: 100%;
    height: 100%;
    min-height: 160px;
  }

  .viewport :global(canvas) {
    display: block;
    width: 100% !important;
    height: 100% !important;
  }

  .hud {
    position: absolute;
    bottom: 14px;
    left: 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px 14px;
    padding: 7px 12px;
    border-radius: var(--radius-sm);
    background: rgba(10, 15, 25, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #f8fafc;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    pointer-events: none;
    backdrop-filter: blur(6px);
  }

  .k {
    color: #94a3b8;
    font-weight: 600;
    margin-right: 3px;
  }

  .tags {
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: flex-end;
    pointer-events: none;
  }

  .tags span {
    font-size: 10px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: var(--radius-pill);
    background: rgba(220, 38, 38, 0.85);
    color: #fff;
    text-transform: capitalize;
  }

  .badge-3d {
    position: absolute;
    top: 10px;
    left: 10px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #cbd5e1;
    padding: 4px 8px;
    border-radius: var(--radius-pill);
    background: rgba(10, 15, 25, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.1);
    pointer-events: none;
    backdrop-filter: blur(4px);
  }
</style>
