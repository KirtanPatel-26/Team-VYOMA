/**
 * SmartRetail AI - 3D Immersive Store Digital Twin Engine
 * Framework: Three.js + GSAP + Real Edge AI FastAPI Telemetry
 */

// Scene Globals
let scene, camera, renderer, controls;
let raycaster, mouse;
let shelfMeshes = [];
let productBoxes = [];
let personAvatars = {};
let queueAvatars = [];
let heatmapMesh, heatmapCanvas, heatmapCtx, heatmapTexture;
let thermalPillars = [];
let cctvTexture, cctvCanvas, cctvCtx;
let showHeatmap = true;
let showLabels = true;

// Camera Flythrough Presets
const CAMERA_PRESETS = {
  overview: { pos: { x: 0, y: 20, z: 24 }, target: { x: 0, y: 0, z: 0 } },
  shelfA:   { pos: { x: -7, y: 4, z: -1 }, target: { x: -7, y: 1.8, z: -5 } },
  shelfB:   { pos: { x: -7, y: 4, z: 9 },  target: { x: -7, y: 1.8, z: 5 } },
  shelfC:   { pos: { x: 7, y: 4, z: -1 },  target: { x: 7, y: 1.8, z: -5 } },
  queue:    { pos: { x: 7, y: 4, z: 10 },  target: { x: 7, y: 1.5, z: 5 } },
  cctv:     { pos: { x: 0, y: 5.5, z: -4 }, target: { x: 0, y: 5.5, z: -11.5 } }
};

// Initial Setup
window.addEventListener("DOMContentLoaded", () => {
  init3DScene();
  setupLighting();
  buildStoreEnvironment();
  buildShelfRacks();
  buildCheckoutQueueZone();
  buildCCTVScreenMesh();
  buildHeatmapLayer();
  buildThermalPillars();
  setupInteractivity();
  startDataPolling();
  animate();
});

// 1. Scene & Renderer Initialization
function init3DScene() {
  const canvas = document.getElementById("webgl-canvas");
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0f1d);
  scene.fog = new THREE.FogExp2(0x0a0f1d, 0.025);

  camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 200);
  camera.position.set(0, 20, 24);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.maxPolarAngle = Math.PI / 2.05; // don't go below floor
  controls.minDistance = 4;
  controls.maxDistance = 45;
  controls.target.set(0, 0, 0);

  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();

  window.addEventListener("resize", onWindowResize);
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

// 2. Realistic Retail Store Lighting
function setupLighting() {
  const ambient = new THREE.AmbientLight(0xffffff, 0.55);
  scene.add(ambient);

  // Main directional sunlight / high bay spotlight
  const dirLight = new THREE.DirectionalLight(0xfff8ee, 0.85);
  dirLight.position.set(10, 25, 15);
  dirLight.castShadow = true;
  dirLight.shadow.mapSize.width = 2048;
  dirLight.shadow.mapSize.height = 2048;
  dirLight.shadow.camera.near = 5;
  dirLight.shadow.camera.far = 50;
  dirLight.shadow.camera.left = -20;
  dirLight.shadow.camera.right = 20;
  dirLight.shadow.camera.top = 20;
  dirLight.shadow.camera.bottom = -20;
  scene.add(dirLight);

  // Soft colored accent lights above aisles
  const aisleLight1 = new THREE.PointLight(0x38bdf8, 1.2, 18);
  aisleLight1.position.set(-7, 6, 0);
  scene.add(aisleLight1);

  const aisleLight2 = new THREE.PointLight(0x6366f1, 1.2, 18);
  aisleLight2.position.set(7, 6, 0);
  scene.add(aisleLight2);
}

// 3. Store Architecture (Floor, Walls, Aisle Ceilings)
function buildStoreEnvironment() {
  // Store Floor (28m x 26m)
  const floorGeo = new THREE.PlaneGeometry(28, 26);
  const floorMat = new THREE.MeshStandardMaterial({
    color: 0x131a2b,
    roughness: 0.35,
    metalness: 0.15
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  // Grid lines on floor
  const grid = new THREE.GridHelper(26, 26, 0x1e293b, 0x172033);
  grid.position.y = 0.01;
  scene.add(grid);

  // Back wall
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.7 });
  const backWall = new THREE.Mesh(new THREE.BoxGeometry(28, 8, 0.5), wallMat);
  backWall.position.set(0, 4, -13);
  backWall.receiveShadow = true;
  scene.add(backWall);

  // Accent neon strip on back wall
  const neonMat = new THREE.MeshBasicMaterial({ color: 0x0284c7 });
  const neonStrip = new THREE.Mesh(new THREE.BoxGeometry(26, 0.1, 0.1), neonMat);
  neonStrip.position.set(0, 7.5, -12.7);
  scene.add(neonStrip);

  // Store Entrance & Exit Door Indicators
  const entranceMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });
  const entrance = new THREE.Mesh(new THREE.BoxGeometry(3, 0.05, 0.6), entranceMat);
  entrance.position.set(-12, 0.02, 11);
  scene.add(entrance);

  const exitMat = new THREE.MeshBasicMaterial({ color: 0xf43f5e });
  const exit = new THREE.Mesh(new THREE.BoxGeometry(3, 0.05, 0.6), exitMat);
  exit.position.set(12, 0.02, 11);
  scene.add(exit);
}

// 4. 3D Shelf Racks (Shelf A, Shelf B, Shelf C)
function buildShelfRacks() {
  const rackConfigs = [
    {
      id: "shelfA",
      name: "Shelf A: Snacks & Biscuits",
      pos: { x: -7, z: -5 },
      skus: ["SKU002", "SKU003", "SKU008", "SKU009"],
      color: 0xf59e0b
    },
    {
      id: "shelfB",
      name: "Shelf B: Beverages & Juices",
      pos: { x: -7, z: 5 },
      skus: ["SKU001", "SKU005", "SKU007"],
      color: 0x0284c7
    },
    {
      id: "shelfC",
      name: "Shelf C: Dairy & Essentials",
      pos: { x: 7, z: -5 },
      skus: ["SKU004", "SKU006", "SKU010"],
      color: 0x10b981
    }
  ];

  rackConfigs.forEach(cfg => {
    const rackGroup = new THREE.Group();
    rackGroup.position.set(cfg.pos.x, 0, cfg.pos.z);

    // Frame (black metal uprights)
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.2 });
    for (let dx of [-3.5, 3.5]) {
      for (let dz of [-0.9, 0.9]) {
        const post = new THREE.Mesh(new THREE.BoxGeometry(0.12, 4.0, 0.12), frameMat);
        post.position.set(dx, 2.0, dz);
        post.castShadow = true;
        rackGroup.add(post);
      }
    }

    // Shelving Boards (3 Levels: y=0.4, y=1.6, y=2.8)
    const shelfBoardMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.5 });
    const shelfLevels = [0.4, 1.6, 2.8];
    shelfLevels.forEach(lvl => {
      const board = new THREE.Mesh(new THREE.BoxGeometry(7.2, 0.08, 1.9), shelfBoardMat);
      board.position.set(0, lvl, 0);
      board.receiveShadow = true;
      rackGroup.add(board);
    });

    // Top Aisle Sign Header
    const signMat = new THREE.MeshStandardMaterial({ color: cfg.color, roughness: 0.3 });
    const sign = new THREE.Mesh(new THREE.BoxGeometry(7.2, 0.5, 0.1), signMat);
    sign.position.set(0, 4.0, 0);
    rackGroup.add(sign);

    // Add Product Blocks onto the shelf levels
    const skuList = cfg.skus;
    skuList.forEach((sku, idx) => {
      const xOffset = -2.6 + idx * (5.2 / Math.max(1, skuList.length - 1));
      
      // Each SKU gets a 3D block stack representation
      const boxGeo = new THREE.BoxGeometry(1.0, 0.9, 0.7);
      const boxMat = new THREE.MeshStandardMaterial({
        color: 0x10b981,
        roughness: 0.4,
        metalness: 0.2
      });
      const prodBox = new THREE.Mesh(boxGeo, boxMat);
      prodBox.position.set(xOffset, 1.6 + 0.45, 0);
      prodBox.castShadow = true;
      prodBox.receiveShadow = true;

      // Attach SKU metadata to 3D object for raycaster
      prodBox.userData = {
        sku_id: sku,
        shelf_id: cfg.id,
        shelf_name: cfg.name,
        product_name: "Loading...",
        stock: 4,
        min_stock: 2,
        price: 35,
        status: "IN_STOCK"
      };

      rackGroup.add(prodBox);
      productBoxes.push(prodBox);
    });

    scene.add(rackGroup);
    shelfMeshes.push(rackGroup);
  });
}

// 5. Checkout Counters & Queue Stanchions Zone
let queueGroup;
function buildCheckoutQueueZone() {
  queueGroup = new THREE.Group();
  queueGroup.position.set(7, 0, 5);

  // Counter desk
  const counterMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.3 });
  const desk = new THREE.Mesh(new THREE.BoxGeometry(4.0, 1.1, 1.8), counterMat);
  desk.position.set(0, 0.55, 0);
  desk.castShadow = true;
  desk.receiveShadow = true;
  queueGroup.add(desk);

  // POS Touch Terminal
  const screenMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
  const posScreen = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.4, 0.05), screenMat);
  posScreen.position.set(0.6, 1.35, 0.2);
  posScreen.rotation.x = -0.3;
  queueGroup.add(posScreen);

  // Queue Lane Waiting Zone boundary on floor
  const laneMat = new THREE.MeshBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.25 });
  const laneFloor = new THREE.Mesh(new THREE.PlaneGeometry(3.5, 5.0), laneMat);
  laneFloor.rotation.x = -Math.PI / 2;
  laneFloor.position.set(0, 0.02, 3.5);
  queueGroup.add(laneFloor);

  // Stanchion posts (brass poles)
  const poleMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.9, roughness: 0.2 });
  const ropeMat = new THREE.MeshStandardMaterial({ color: 0xbe123c, roughness: 0.8 });

  for (let z of [1.5, 3.5, 5.5]) {
    for (let x of [-1.8, 1.8]) {
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.06, 1.0, 12), poleMat);
      pole.position.set(x, 0.5, z);
      pole.castShadow = true;
      queueGroup.add(pole);
    }
  }

  scene.add(queueGroup);
}

// 6. CCTV Monitor Wall Mesh (Canvas-projected Video Feed)
function buildCCTVScreenMesh() {
  cctvCanvas = document.createElement("canvas");
  cctvCanvas.width = 640;
  cctvCanvas.height = 360;
  cctvCtx = cctvCanvas.getContext("2d");

  // Initial placeholder text
  cctvCtx.fillStyle = "#020617";
  cctvCtx.fillRect(0, 0, 640, 360);
  cctvCtx.fillStyle = "#38bdf8";
  cctvCtx.font = "bold 24px monospace";
  cctvCtx.fillText("SmartRetail Edge AI CCTV Feed", 100, 180);

  cctvTexture = new THREE.CanvasTexture(cctvCanvas);

  const screenGroup = new THREE.Group();
  screenGroup.position.set(0, 5.5, -12.65);

  // Monitor Bezel Frame
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x020617, metalness: 0.7, roughness: 0.2 });
  const frame = new THREE.Mesh(new THREE.BoxGeometry(6.4, 3.8, 0.2), frameMat);
  screenGroup.add(frame);

  // Monitor Display Screen
  const screenMat = new THREE.MeshBasicMaterial({ map: cctvTexture });
  const display = new THREE.Mesh(new THREE.PlaneGeometry(6.0, 3.4), screenMat);
  display.position.z = 0.11;
  screenGroup.add(display);

  scene.add(screenGroup);
}

// 7. Dynamic Floor Heatmap Layer with Smooth Upscaling
function buildHeatmapLayer() {
  heatmapCanvas = document.createElement("canvas");
  heatmapCanvas.width = 144;
  heatmapCanvas.height = 80;
  heatmapCtx = heatmapCanvas.getContext("2d");

  heatmapTexture = new THREE.CanvasTexture(heatmapCanvas);
  heatmapTexture.minFilter = THREE.LinearFilter;
  heatmapTexture.magFilter = THREE.LinearFilter;

  const heatMat = new THREE.MeshBasicMaterial({
    map: heatmapTexture,
    transparent: true,
    opacity: 0.72,
    depthWrite: false
  });

  const heatGeo = new THREE.PlaneGeometry(26, 22);
  heatmapMesh = new THREE.Mesh(heatGeo, heatMat);
  heatmapMesh.rotation.x = -Math.PI / 2;
  heatmapMesh.position.y = 0.03;
  scene.add(heatmapMesh);
}

// 7b. Volumetric 3D Thermal Dwell Pillars over Retail Zones
function buildThermalPillars() {
  const pillarConfigs = [
    { id: "shelfA", name: "Shelf A (Snacks)", pos: { x: -7, z: -5 }, color: 0xf59e0b, radius: 2.2 },
    { id: "shelfB", name: "Shelf B (Beverages)", pos: { x: -7, z: 5 }, color: 0x06b6d4, radius: 2.2 },
    { id: "shelfC", name: "Shelf C (Dairy)", pos: { x: 7, z: -5 }, color: 0x10b981, radius: 2.2 },
    { id: "queue",  name: "Queue Zone", pos: { x: 7, z: 5 }, color: 0xf43f5e, radius: 2.4 },
    { id: "entrance", name: "Entrance", pos: { x: -12, z: 11 }, color: 0x8b5cf6, radius: 1.8 }
  ];

  pillarConfigs.forEach(cfg => {
    const group = new THREE.Group();
    group.position.set(cfg.pos.x, 0.04, cfg.pos.z);

    // 1. Ground pulsing ring
    const ringGeo = new THREE.RingGeometry(cfg.radius * 0.75, cfg.radius * 1.05, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: cfg.color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.45,
      depthWrite: false
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = -Math.PI / 2;
    group.add(ringMesh);

    // 2. Volumetric translucent thermal cylinder
    const cylGeo = new THREE.CylinderGeometry(cfg.radius, cfg.radius * 0.9, 3.0, 32, 1, true);
    const cylMat = new THREE.MeshBasicMaterial({
      color: cfg.color,
      transparent: true,
      opacity: 0.16,
      side: THREE.DoubleSide,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    const cylMesh = new THREE.Mesh(cylGeo, cylMat);
    cylMesh.position.y = 1.5;
    group.add(cylMesh);

    // 3. Top floating halo ring
    const topRingGeo = new THREE.RingGeometry(cfg.radius * 0.9, cfg.radius, 32);
    const topRingMat = new THREE.MeshBasicMaterial({
      color: cfg.color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.55,
      depthWrite: false
    });
    const topRingMesh = new THREE.Mesh(topRingGeo, topRingMat);
    topRingMesh.rotation.x = -Math.PI / 2;
    topRingMesh.position.y = 3.0;
    group.add(topRingMesh);

    scene.add(group);
    thermalPillars.push({
      id: cfg.id,
      name: cfg.name,
      group: group,
      cyl: cylMesh,
      ring: ringMesh,
      topRing: topRingMesh,
      baseRadius: cfg.radius,
      targetHeight: 2.8,
      currentHeight: 2.8
    });
  });
}

function updateThermalPillars(traffic) {
  if (!traffic) return;
  const dwellSummary = traffic.zone_dwell_summary || {};

  thermalPillars.forEach(pillar => {
    let dwellVal = 0;
    for (const [k, v] of Object.entries(dwellSummary)) {
      const lowerK = k.toLowerCase();
      if (lowerK.includes(pillar.id.toLowerCase()) || (pillar.id === "queue" && lowerK.includes("queue"))) {
        dwellVal = Math.max(dwellVal, Number(v) || 0);
      }
    }
    const normVal = Math.min(2.5, Math.max(0.2, dwellVal / 45.0));
    pillar.targetHeight = Math.max(0.8, Math.min(5.2, 1.4 + normVal * 2.0));
  });
}

// Update Heatmap canvas from API grid with smooth interpolation & high-contrast thermal palette
function updateHeatmapTexture(gridData) {
  if (!gridData || !gridData.length) return;
  const rows = gridData.length;
  const cols = gridData[0].length;

  if (!window._lowResHeatCanvas) {
    window._lowResHeatCanvas = document.createElement("canvas");
  }
  const lowCanvas = window._lowResHeatCanvas;
  if (lowCanvas.width !== cols || lowCanvas.height !== rows) {
    lowCanvas.width = cols;
    lowCanvas.height = rows;
  }
  const lowCtx = lowCanvas.getContext("2d");
  const imgData = lowCtx.createImageData(cols, rows);

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const val = gridData[r][c] || 0.0;
      const idx = (r * cols + c) * 4;

      if (val < 0.035) {
        imgData.data[idx] = 0;
        imgData.data[idx + 1] = 0;
        imgData.data[idx + 2] = 0;
        imgData.data[idx + 3] = 0;
      } else {
        // High-contrast multi-stop thermal palette:
        // Navy/Electric Cyan -> Vibrant Emerald -> Bright Amber -> Hot Crimson
        let red = 0, green = 0, blue = 0, alpha = 0;
        if (val < 0.25) {
          const t = (val - 0.035) / (0.25 - 0.035);
          red = Math.floor(10 + t * 4);
          green = Math.floor(120 + t * 90);
          blue = Math.floor(220 + t * 35);
          alpha = Math.floor(65 + t * 85);
        } else if (val < 0.5) {
          const t = (val - 0.25) / 0.25;
          red = Math.floor(14 + t * 20);
          green = Math.floor(210 - t * 13);
          blue = Math.floor(255 - t * 160);
          alpha = Math.floor(150 + t * 45);
        } else if (val < 0.75) {
          const t = (val - 0.5) / 0.25;
          red = Math.floor(34 + t * 211);
          green = Math.floor(197 - t * 39);
          blue = Math.floor(95 - t * 84);
          alpha = Math.floor(195 + t * 35);
        } else {
          const t = Math.min(1.0, (val - 0.75) / 0.25);
          red = Math.floor(245 - t * 6);
          green = Math.floor(158 - t * 90);
          blue = Math.floor(11 + t * 57);
          alpha = Math.floor(230 + t * 25);
        }

        imgData.data[idx] = red;
        imgData.data[idx + 1] = green;
        imgData.data[idx + 2] = blue;
        imgData.data[idx + 3] = alpha;
      }
    }
  }

  lowCtx.putImageData(imgData, 0, 0);

  // Smoothly upscale to the main heatmap canvas for silky-smooth contours
  heatmapCtx.clearRect(0, 0, heatmapCanvas.width, heatmapCanvas.height);
  heatmapCtx.imageSmoothingEnabled = true;
  heatmapCtx.imageSmoothingQuality = "high";
  heatmapCtx.drawImage(lowCanvas, 0, 0, heatmapCanvas.width, heatmapCanvas.height);

  heatmapTexture.needsUpdate = true;
}

// 8. Shoppers & Staff 3D Avatars (Interpolated Motion)
function updatePersonAvatars(activeTracks) {
  const currentIds = new Set();

  (activeTracks || []).forEach(track => {
    const tid = track.track_id;
    if (!tid) return;
    currentIds.add(tid);

    // Map normalized camera (x, y) [0..1] to 3D store coordinates
    // Store floor: X in [-10, 10], Z in [-8, 8]
    const targetX = (track.x - 0.5) * 22.0;
    const targetZ = (track.y - 0.5) * 16.0;

    let avatar = personAvatars[tid];
    if (!avatar) {
      // Create new avatar
      const isStaff = (track.type === "staff");
      const avatarGroup = new THREE.Group();

      const color = isStaff ? 0xfbbf24 : 0x38bdf8;
      const bodyMat = new THREE.MeshStandardMaterial({
        color: color,
        roughness: 0.3,
        emissive: color,
        emissiveIntensity: 0.25
      });

      // Capsule body
      const body = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 1.2, 16), bodyMat);
      body.position.y = 0.7;
      body.castShadow = true;
      avatarGroup.add(body);

      // Head
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.24, 16, 16), bodyMat);
      head.position.y = 1.45;
      avatarGroup.add(head);

      // Ground pulse ring
      const ringMat = new THREE.MeshBasicMaterial({ color: color, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.35, 0.45, 16), ringMat);
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.04;
      avatarGroup.add(ring);

      avatarGroup.position.set(targetX, 0, targetZ);
      scene.add(avatarGroup);

      avatar = {
        group: avatarGroup,
        targetPos: new THREE.Vector3(targetX, 0, targetZ),
        type: track.type
      };
      personAvatars[tid] = avatar;
    } else {
      avatar.targetPos.set(targetX, 0, targetZ);
    }
  });

  // Remove avatars that left view
  for (const [tid, avatar] of Object.entries(personAvatars)) {
    if (!currentIds.has(parseInt(tid))) {
      scene.remove(avatar.group);
      delete personAvatars[tid];
    }
  }
}

// 9. Update Checkout Queue Avatars
function updateQueueVisualizer(queueLength, isCongested) {
  // Add or remove queue avatars
  while (queueAvatars.length < queueLength && queueAvatars.length < 8) {
    const qIdx = queueAvatars.length;
    const qColor = isCongested ? 0xf43f5e : 0x38bdf8;
    const qMat = new THREE.MeshStandardMaterial({ color: qColor, roughness: 0.4 });
    const qPerson = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 1.2, 12), qMat);
    qPerson.position.set(7, 0.65, 6.2 + qIdx * 0.9);
    qPerson.castShadow = true;
    scene.add(qPerson);
    queueAvatars.push(qPerson);
  }

  while (queueAvatars.length > queueLength) {
    const removed = queueAvatars.pop();
    scene.remove(removed);
  }

  // Update color if congested
  const activeColor = isCongested ? 0xf43f5e : 0x38bdf8;
  queueAvatars.forEach(q => {
    q.material.color.setHex(activeColor);
  });
}

// 10. Raycasting & Tooltip Interactivity
let latestBrainMap = {};
let activeSelectedProduct = null;

// 10. Raycasting & Tooltip Interactivity + Click to Inspect XAI
function setupInteractivity() {
  const tooltip = document.getElementById("tooltip-3d");

  window.addEventListener("mousemove", (event) => {
    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(productBoxes);

    if (intersects.length > 0) {
      const obj = intersects[0].object;
      const data = obj.userData;

      document.getElementById("ttTitle").innerText = data.product_name || "Unknown";
      document.getElementById("ttSku").innerText = `${data.sku_id} • ${data.shelf_name || 'Shelf'}`;
      document.getElementById("ttStock").innerText = data.stock;
      document.getElementById("ttMin").innerText = data.min_stock;
      document.getElementById("ttPrice").innerText = `₹${data.price}`;
      
      const ttStatus = document.getElementById("ttStatus");
      ttStatus.innerText = data.status;
      ttStatus.style.color = data.status === "IN_STOCK" ? "#34d399" : (data.status === "LOW_STOCK" ? "#fbbf24" : "#f43f5e");

      tooltip.style.left = `${event.clientX}px`;
      tooltip.style.top = `${event.clientY}px`;
      tooltip.style.display = "block";
      document.body.style.cursor = "pointer";
    } else {
      tooltip.style.display = "none";
      document.body.style.cursor = "default";
    }
  });

  // Click on product in 3D scene -> Cinematic Camera Fly & Explainable AI Modal
  window.addEventListener("click", (event) => {
    if (event.target.closest(".hud-header") || event.target.closest(".hud-left") || event.target.closest(".hud-bottom-right") || event.target.closest("#xaiModal")) {
      return;
    }

    mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(productBoxes);

    if (intersects.length > 0) {
      const obj = intersects[0].object;
      focusOnProductBox(obj);
    }
  });
}

function focusOnProductBox(box) {
  activeSelectedProduct = box.userData;
  const worldPos = new THREE.Vector3();
  box.getWorldPosition(worldPos);

  // Cinematic offset depending on aisle side
  const offsetX = worldPos.x < 0 ? 2.8 : -2.8;
  const targetCamPos = new THREE.Vector3(worldPos.x + offsetX, worldPos.y + 1.2, worldPos.z + 2.2);

  gsap.to(camera.position, {
    x: targetCamPos.x,
    y: targetCamPos.y,
    z: targetCamPos.z,
    duration: 1.6,
    ease: "power2.inOut"
  });

  gsap.to(controls.target, {
    x: worldPos.x,
    y: worldPos.y,
    z: worldPos.z,
    duration: 1.6,
    ease: "power2.inOut"
  });

  openXaiModal(box.userData);
}

function openXaiModal(data) {
  const modal = document.getElementById("xaiModal");
  if (!modal) return;

  const sku = data.sku_id;
  const brainInfo = latestBrainMap[sku] || {};

  document.getElementById("xaiTitle").innerText = data.product_name || sku;
  document.getElementById("xaiSub").innerText = `${sku} • ${data.shelf_name || 'Shelf Bay'}`;

  const currentStock = data.stock !== undefined ? data.stock : (brainInfo.current_stock || 0);
  const minStock = data.min_stock !== undefined ? data.min_stock : (brainInfo.min_stock || 2);
  document.getElementById("xaiStock").innerText = `${currentStock} units (Min: ${minStock})`;

  const eta = brainInfo.stockout_eta_formatted || (currentStock === 0 ? "0m (DEPLETED)" : "Optimal");
  document.getElementById("xaiEta").innerText = eta;

  const vel = brainInfo.sales_velocity_hourly || 1.4;
  document.getElementById("xaiVelocity").innerText = `${vel} units/hr`;

  const revRisk = brainInfo.revenue_at_risk || (data.price * 4);
  document.getElementById("xaiRevAtRisk").innerText = `₹${revRisk.toFixed(2)}`;

  const risk = brainInfo.risk_level || (currentStock === 0 ? "CRITICAL" : (currentStock <= minStock ? "HIGH" : "OPTIMAL"));
  const riskBadge = document.getElementById("xaiRiskBadge");
  riskBadge.innerText = risk;
  if (risk === "CRITICAL") {
    riskBadge.style.background = "rgba(244,63,94,0.15)";
    riskBadge.style.color = "#f43f5e";
    riskBadge.style.borderColor = "#f43f5e";
  } else if (risk === "HIGH") {
    riskBadge.style.background = "rgba(245,158,11,0.15)";
    riskBadge.style.color = "#fbbf24";
    riskBadge.style.borderColor = "#fbbf24";
  } else {
    riskBadge.style.background = "rgba(16,185,129,0.15)";
    riskBadge.style.color = "#34d399";
    riskBadge.style.borderColor = "#10b981";
  }

  const whyText = brainInfo.why_reasoning || (
    currentStock === 0
      ? `• Stock completely depleted on shelf.\n• Consumption velocity was ${vel} units/hr.\n• Customer walkout risk imminent.`
      : `• Shelf buffer at ${currentStock} units.\n• Velocity: ${vel} units/hour.\n• Predicted runtime remaining: ${eta}.`
  );
  document.getElementById("xaiReasoning").innerText = whyText;

  const actionText = brainInfo.recommended_action || (
    currentStock === 0
      ? `Refill ${data.product_name} IMMEDIATELY (+${minStock * 2} units)`
      : `Monitor inventory buffer on shelf.`
  );
  document.getElementById("xaiAction").innerText = actionText;

  modal.style.display = "block";
}

window.closeXaiModal = function() {
  const modal = document.getElementById("xaiModal");
  if (modal) modal.style.display = "none";
};

window.dispatchReplenishmentFromModal = async function() {
  if (!activeSelectedProduct) return;
  const btn = document.getElementById("btnXaiDispatch");
  btn.innerText = "⏳ Dispatching...";
  try {
    const res = await fetch("/api/staff/dispatch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: `Restock ${activeSelectedProduct.product_name} (${activeSelectedProduct.sku_id}) immediately`,
        staff: "Staff #201 - Floor Associate"
      })
    });
    const result = await res.json();
    btn.innerText = "✅ Associate Dispatched!";
    setTimeout(() => {
      btn.innerText = "🚀 Dispatch Floor Staff";
      closeXaiModal();
    }, 1400);
  } catch (err) {
    btn.innerText = "⚠️ Dispatch Error";
    setTimeout(() => { btn.innerText = "🚀 Dispatch Floor Staff"; }, 1500);
  }
};

// 11. Camera Fly-through with GSAP
window.flyToPerspective = function(presetKey) {
  const preset = CAMERA_PRESETS[presetKey];
  if (!preset) return;

  document.querySelectorAll(".btn-cam").forEach(b => b.classList.remove("active"));
  const clickedBtn = event ? event.target.closest(".btn-cam") : null;
  if (clickedBtn) clickedBtn.classList.add("active");

  gsap.to(camera.position, {
    x: preset.pos.x,
    y: preset.pos.y,
    z: preset.pos.z,
    duration: 1.8,
    ease: "power2.inOut"
  });

  gsap.to(controls.target, {
    x: preset.target.x,
    y: preset.target.y,
    z: preset.target.z,
    duration: 1.8,
    ease: "power2.inOut"
  });
};

// Toggle layers
window.toggleHeatmap = function() {
  showHeatmap = !showHeatmap;
  if (heatmapMesh) heatmapMesh.visible = showHeatmap;
  thermalPillars.forEach(p => {
    if (p.group) p.group.visible = showHeatmap;
  });
  document.getElementById("toggleHeatmapBtn").innerText = `🔥 Heatmap: ${showHeatmap ? 'ON' : 'OFF'}`;
};

window.toggleLabels = function() {
  showLabels = !showLabels;
  document.getElementById("toggleLabelsBtn").innerText = `🏷️ Labels: ${showLabels ? 'ON' : 'OFF'}`;
};

// 12. Real-time Data Polling Loop
function startDataPolling() {
  async function poll() {
    try {
      // 1. Fetch system status & Honest Detection Mode
      const statusRes = await fetch("/api/status");
      if (statusRes.ok) {
        const sData = await statusRes.json();
        const modeBadge = document.getElementById("modeBadge");
        const modeLabel = document.getElementById("modeLabel");
        if (sData.detection_mode === "TRAINED_MODEL") {
          modeBadge.className = "mode-badge trained";
          modeLabel.innerText = "● MODE: TRAINED MODEL (best.pt)";
        } else {
          modeBadge.className = "mode-badge simulation";
          modeLabel.innerText = "▲ MODE: DEMO SIMULATION (Fallback CV)";
        }
      }

      // 2. Fetch Live Stats (Inventory, Traffic, Queue, Alerts)
      const statsRes = await fetch("/api/live-stats");
      if (statsRes.ok) {
        const data = await statsRes.json();

        // Update KPIs
        const traffic = data.traffic || {};
        document.getElementById("kpiCustomers").innerText = traffic.current_customers || 0;
        document.getElementById("kpiStaff").innerText = `${traffic.current_staff || 0} (${traffic.customer_to_staff_ratio || '1:1'})`;

        const stockRep = data.stock || {};
        document.getElementById("kpiStockHealth").innerText = `${stockRep.stock_health_score || 100}%`;

        const queueRep = data.queue || {};
        document.getElementById("kpiQueueLen").innerText = queueRep.queue_length || 0;

        // Update Product 3D Blocks based on inventory
        const items = stockRep.items || [];
        productBoxes.forEach(box => {
          const sku = box.userData.sku_id;
          const match = items.find(i => i.product_id === sku);
          if (match) {
            box.userData.product_name = match.product_name;
            box.userData.stock = match.stock;
            box.userData.min_stock = match.minimum_stock;
            box.userData.price = match.price;
            box.userData.status = match.status;

            // Update color based on stock status
            if (match.status === "IN_STOCK") {
              box.material.color.setHex(0x10b981); // Emerald
            } else if (match.status === "LOW_STOCK") {
              box.material.color.setHex(0xf59e0b); // Amber
            } else {
              box.material.color.setHex(0xf43f5e); // Rose / Red
            }

            // Scale height dynamically based on stock count
            const targetHeight = Math.max(0.2, (match.stock / Math.max(1, match.minimum_stock * 2)) * 1.1);
            box.scale.y = targetHeight;
          }
        });

        // Update Heatmap & Volumetric Thermal Pillars
        if (traffic.heatmap_grid) {
          updateHeatmapTexture(traffic.heatmap_grid);
        }
        updateThermalPillars(traffic);

        // Update Person Avatars
        if (traffic.active_tracks) {
          updatePersonAvatars(traffic.active_tracks);
        }

        // Update Queue Avatars
        updateQueueVisualizer(queueRep.queue_length || 0, queueRep.congestion || false);

        // Update Business Impact ROI Ticker
        const roi = data.business_impact || {};
        const roiProtElem = document.getElementById("roiProtected");
        const roiLostElem = document.getElementById("roiLost");
        if (roiProtElem) {
          const protVal = Math.round(roi.revenue_protected_today || 0);
          roiProtElem.innerText = `₹${protVal.toLocaleString()}`;
        }
        if (roiLostElem) {
          const lostVal = Math.round(roi.total_estimated_lost_sales_today || 0);
          roiLostElem.innerText = `₹${lostVal.toLocaleString()}`;
        }

        // Cache Store Brain predictions for XAI inspection
        if (data.brain && data.brain.sku_predictions) {
          data.brain.sku_predictions.forEach(p => {
            latestBrainMap[p.sku_id] = p;
          });
        }

        // Update Alerts
        const alerts = data.alerts || [];
        document.getElementById("alertsCountBadge").innerText = alerts.length;
        const alertsList = document.getElementById("alertsList");
        if (alerts.length === 0) {
          alertsList.innerHTML = '<div style="color: #10b981; font-size: 11px; padding: 6px;">All store parameters optimal.</div>';
        } else {
          alertsList.innerHTML = alerts.slice(0, 5).map(a => `
            <div class="alert-entry ${a.severity || 'warning'}">
              <div class="alert-title">
                <span>${a.title}</span>
                <span style="font-size: 9px; color: #64748b;">${a.timestamp || ''}</span>
              </div>
              <div class="alert-msg">${a.message}</div>
            </div>
          `).join("");
        }
      }
    } catch (err) {
      console.warn("[3D Twin] Telemetry polling pause:", err);
    }

    setTimeout(poll, 1500);
  }

  poll();
}

// 13. Render & Animation Loop
function animate() {
  requestAnimationFrame(animate);

  controls.update();

  // Smooth lerp for person avatars
  for (const avatar of Object.values(personAvatars)) {
    avatar.group.position.lerp(avatar.targetPos, 0.08);
  }

  // Dynamic breathing/pulsing animation for 3D thermal pillars
  const time = Date.now() * 0.0025;
  thermalPillars.forEach((p, idx) => {
    p.currentHeight += (p.targetHeight - p.currentHeight) * 0.06;
    const pulse = Math.sin(time + idx * 1.3) * 0.05;
    p.cyl.scale.set(1.0 + pulse, p.currentHeight / 3.0, 1.0 + pulse);
    p.cyl.position.y = p.currentHeight / 2.0;
    p.topRing.position.y = p.currentHeight;
    p.ring.scale.setScalar(1.0 + Math.sin(time * 1.8 + idx) * 0.08);
  });

  // Update in-scene CCTV video texture from offscreen image
  const cctvImg = document.getElementById("cctv-stream-source");
  if (cctvImg && cctvImg.naturalWidth > 0 && cctvCtx) {
    try {
      cctvCtx.drawImage(cctvImg, 0, 0, 640, 360);
      cctvTexture.needsUpdate = true;
    } catch (e) {}
  }

  renderer.render(scene, camera);
}
