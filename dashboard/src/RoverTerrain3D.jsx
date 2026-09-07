import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// Real elevation data from the actual DEM (terrain/dem_loader.py via the
// backend's /terrain-heightmap endpoint) is stretched vertically so relief
// is actually visible - flat DEM patches otherwise look like a plate at
// realistic 1:1 scale. This is a visualization exaggeration only; the
// underlying values served by the backend are the genuine measured
// elevations, unexaggerated.
const VERTICAL_EXAGGERATION = 3;

// Cache fetched heightmaps across component mounts/unmounts (e.g. toggling
// between the 2D and 3D view) so switching back doesn't refetch/rebuild.
const heightmapCache = new Map();

function closestIndex(arr, val) {
  // arr is monotonic (increasing or decreasing) - binary search for the
  // nearest grid line, used to sample terrain height under a world (x,y).
  let lo = 0, hi = arr.length - 1;
  const increasing = arr[hi] > arr[0];
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    const cond = increasing ? arr[mid] < val : arr[mid] > val;
    if (cond) lo = mid + 1; else hi = mid;
  }
  return lo;
}

export default function RoverTerrain3D({ apiBase, trail, position, uncertainty, mode }) {
  const mountRef = useRef(null);
  const sceneStateRef = useRef(null);
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  // ---- one-time scene setup + real DEM heightmap fetch ----
  useEffect(() => {
    const mountEl = mountRef.current;
    if (!mountEl) return;
    let cancelled = false;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x03040a);

    const camera = new THREE.PerspectiveCamera(50, mountEl.clientWidth / Math.max(mountEl.clientHeight, 1), 0.1, 100000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mountEl.clientWidth, mountEl.clientHeight);
    mountEl.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;
    controls.minDistance = 5;
    controls.maxDistance = 5000;

    // Lighting: a low, warm "sun" (grazing polar illumination is realistic
    // for the lunar south pole this DEM covers) plus a cool ambient fill
    // so the unlit side of craters isn't pure black.
    const sun = new THREE.DirectionalLight(0xfff2d9, 1.5);
    sun.position.set(-1, 0.4, 0.6);
    scene.add(sun);
    scene.add(new THREE.AmbientLight(0x30405a, 0.7));
    scene.add(new THREE.HemisphereLight(0x223355, 0x0a0a0a, 0.4));

    // Starfield backdrop (decorative only, not real astrometric data)
    const starGeo = new THREE.BufferGeometry();
    const starCount = 2000;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const r = 3000 + Math.random() * 3000;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      starPos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      starPos[i * 3 + 1] = Math.abs(r * Math.cos(phi)) + 200;
      starPos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false }));
    scene.add(stars);

    const s = {
      scene, camera, renderer, controls,
      roverMesh: null, uncertaintyRing: null, trailLine: null,
      xCoords: null, yCoords: null, elevation: null,
      sampleHeight: () => 0,
      targetPos: new THREE.Vector3(),
      currentPos: new THREE.Vector3(),
      animId: null,
      ready: false,
    };
    sceneStateRef.current = s;

    const onResize = () => {
      if (!mountEl) return;
      camera.aspect = mountEl.clientWidth / Math.max(mountEl.clientHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(mountEl.clientWidth, mountEl.clientHeight);
    };
    const resizeObserver = new ResizeObserver(onResize);
    resizeObserver.observe(mountEl);

    const buildTerrain = (data) => {
      const { rows, cols, elevation, x_coords, y_coords } = data;

      const elevFlat = elevation.flat();
      const elevMean = elevFlat.reduce((a, b) => a + b, 0) / elevFlat.length;

      const geo = new THREE.PlaneGeometry(1, 1, cols - 1, rows - 1);
      const posAttr = geo.attributes.position;
      let vi = 0;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const worldX = x_coords[c];
          const worldY = y_coords[r];
          const h = (elevation[r][c] - elevMean) * VERTICAL_EXAGGERATION;
          // three.js is Y-up: elevation goes on Y, the plane itself spans world X/Z.
          posAttr.setXYZ(vi, worldX, h, worldY);
          vi++;
        }
      }
      posAttr.needsUpdate = true;
      geo.computeVertexNormals();

      const mat = new THREE.MeshStandardMaterial({ color: 0x9a9a9a, flatShading: true, roughness: 1.0, metalness: 0.0 });
      const mesh = new THREE.Mesh(geo, mat);
      scene.add(mesh);

      const sampleHeight = (wx, wy) => {
        const c = closestIndex(x_coords, wx);
        const r = closestIndex(y_coords, wy);
        return (elevation[r][c] - elevMean) * VERTICAL_EXAGGERATION;
      };

      s.xCoords = x_coords;
      s.yCoords = y_coords;
      s.elevation = elevation;
      s.sampleHeight = sampleHeight;

      const spanX = Math.abs(x_coords[cols - 1] - x_coords[0]);
      const spanY = Math.abs(y_coords[rows - 1] - y_coords[0]);
      const span = Math.max(spanX, spanY, 10);
      const centerX = (x_coords[0] + x_coords[cols - 1]) / 2;
      const centerY = (y_coords[0] + y_coords[rows - 1]) / 2;

      camera.position.set(centerX + span * 0.35, span * 0.4, centerY + span * 0.35);
      controls.target.set(centerX, 0, centerY);
      controls.update();

      // Rover marker - a small lander-like cone, easy to read against the terrain.
      const markerSize = Math.max(span * 0.012, 2);
      const roverGeo = new THREE.ConeGeometry(markerSize * 0.5, markerSize * 1.3, 8);
      const roverMat = new THREE.MeshStandardMaterial({ color: 0x22d3ee, emissive: 0x0e7490, emissiveIntensity: 0.9 });
      const roverMesh = new THREE.Mesh(roverGeo, roverMat);
      scene.add(roverMesh);
      s.roverMesh = roverMesh;

      // Uncertainty envelope - a flat ring lying on the terrain around the rover, pulses gently.
      const ringGeo = new THREE.RingGeometry(0.9, 1.0, 48);
      ringGeo.rotateX(-Math.PI / 2);
      const modeColor = mode === 'Caution' ? 0xfacc15 : mode === 'Relocalizing' ? 0xf87171 : 0x22d3ee;
      const ringMat = new THREE.MeshBasicMaterial({ color: modeColor, transparent: true, opacity: 0.55, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.userData.baseRadius = 1;
      scene.add(ring);
      s.uncertaintyRing = ring;

      // Trail line, populated by the trail-sync effect below.
      const trailGeo = new THREE.BufferGeometry();
      const trailMat = new THREE.LineBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.85 });
      const line = new THREE.Line(trailGeo, trailMat);
      scene.add(line);
      s.trailLine = line;

      s.currentPos.set(position.x, sampleHeight(position.x, position.y) + markerSize, position.y);
      s.roverMesh.position.copy(s.currentPos);
      s.targetPos.copy(s.currentPos);

      s.ready = true;
    };

    const cacheKey = `${apiBase}/terrain-heightmap`;
    const cached = heightmapCache.get(cacheKey);
    const loadTerrain = cached
      ? Promise.resolve(cached)
      : fetch(`${apiBase}/terrain-heightmap?grid_size=128`)
          .then(res => {
            if (!res.ok) throw new Error(`status ${res.status}`);
            return res.json();
          })
          .then(data => {
            if (data.error) throw new Error(data.error);
            heightmapCache.set(cacheKey, data);
            return data;
          });

    loadTerrain
      .then(data => {
        if (cancelled) return;
        buildTerrain(data);
        setStatus('ready');
      })
      .catch(err => {
        console.error('terrain heightmap fetch failed', err);
        if (!cancelled) { setStatus('error'); setErrorMsg(String(err.message || err)); }
      });

    const clock = new THREE.Clock();
    let pulseT = 0;
    const animate = () => {
      const dt = Math.min(clock.getDelta(), 0.1);
      pulseT += dt;

      if (s.ready && s.roverMesh) {
        // Smoothly glide toward the latest telemetry position rather than
        // snapping - telemetry only arrives ~1x/second, so this is what
        // makes the rover's motion actually read as animated.
        s.currentPos.lerp(s.targetPos, Math.min(1, dt * 2.2));
        s.roverMesh.position.copy(s.currentPos);
        s.roverMesh.rotation.y += dt * 0.6;

        if (s.uncertaintyRing) {
          s.uncertaintyRing.position.set(s.currentPos.x, s.currentPos.y + 0.4, s.currentPos.z);
          const pulse = 1 + 0.08 * Math.sin(pulseT * 2.2);
          const r = s.uncertaintyRing.userData.baseRadius * pulse;
          s.uncertaintyRing.scale.set(r, r, r);
        }
      }

      controls.update();
      renderer.render(scene, camera);
      s.animId = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelled = true;
      if (s.animId) cancelAnimationFrame(s.animId);
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      scene.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose());
          else obj.material.dispose();
        }
      });
      if (mountEl.contains(renderer.domElement)) mountEl.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  // ---- push new telemetry into the scene without rebuilding it ----
  useEffect(() => {
    const s = sceneStateRef.current;
    if (!s || !s.ready) return;
    const groundH = s.sampleHeight(position.x, position.y);
    s.targetPos.set(position.x, groundH + 2, position.y);
    if (s.uncertaintyRing) {
      s.uncertaintyRing.userData.baseRadius = Math.max(uncertainty, 2);
    }
  }, [position.x, position.y, uncertainty]);

  // ---- rebuild the trail line whenever trail history grows ----
  useEffect(() => {
    const s = sceneStateRef.current;
    if (!s || !s.ready || !s.trailLine || trail.length < 2) return;
    const pts = trail.map(p => new THREE.Vector3(p.x, s.sampleHeight(p.x, p.y) + 1.2, p.y));
    s.trailLine.geometry.dispose();
    s.trailLine.geometry = new THREE.BufferGeometry().setFromPoints(pts);
  }, [trail]);

  return (
    <div className="relative w-full h-full">
      <div ref={mountRef} className="w-full h-full" />
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70 text-[10px] text-cyan-300 tracking-widest text-center px-4">
          LOADING REAL DEM TERRAIN MESH FROM BACKEND...
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70 text-[10px] text-red-400 tracking-widest text-center px-4">
          TERRAIN LOAD FAILED: {errorMsg}<br />
          Check that data/Lunar_Map.tiff exists on the backend and /terrain-heightmap responds.
        </div>
      )}
      {status === 'ready' && (
        <div className="absolute bottom-1 right-2 text-[7px] text-gray-500 tracking-widest pointer-events-none">
          REAL DEM &middot; ELEVATION EXAGGERATED {VERTICAL_EXAGGERATION}&times; FOR VISIBILITY
        </div>
      )}
    </div>
  );
}
