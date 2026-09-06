const ClassicCarModelData = {
  id: "classic-sports-coupe",
  name: "Vintage GT Sports Coupe (Circular Wheels & Wheelhouse Braces)",
  category: "Vehicles / Classic Cars",
  description: "102-piece modular vehicle featuring true circular polygon wheels, dedicated structural wheel-arch support braces, and zero-collision parametric joinery.",
  difficulty: "Level 4 — Expert (102 parts)",
  cameraBookmarks: [
    { name: "Three-Quarter Front Stance", eye: [-210, 85, 170], target: [0, 20, 0], dist: 260 },
    { name: "Wheelhouse Arch & Tire Detail", eye: [-72, 35, 90], target: [-72, 14, 40], dist: 70, select: "W-FR-FACE" },
    { name: "Rear Fastback Profile", eye: [210, 95, 150], target: [0, 20, 0], dist: 260, select: "TAIL-01" },
    { name: "Chassis Belly Pan", eye: [0, -130, 50], target: [0, 10, 0], dist: 210, select: "CHASSIS-01" }
  ],
  assemblySteps: [
    { num: 0, title: "Complete GT Coupe", desc: "Fully assembled 102-piece sports coupe." },
    { num: 1, title: "Chassis & Backbone Frame", desc: "Lock center spine and longitudinal ladder rails into the floor pan.", parts: ["CHASSIS-01", "SPINE-01", "FRAME-L", "FRAME-R"] },
    { num: 2, title: "Transverse Cross Bulkheads", desc: "Slot eight vertical form bulkheads along the spine.", parts: ["BLK-01", "BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07", "BLK-08"] },
    { num: 3, title: "Sill Stringers & Wheel Arch Braces", desc: "Interlock rocker sills, waist stringers, and 4 wheelhouse cover supports.", parts: ["SILL-L", "SILL-R", "WAIST-L", "WAIST-R", "ARCH-BRACE-FL", "ARCH-BRACE-FR", "ARCH-BRACE-RL", "ARCH-BRACE-RR"] },
    { num: 4, title: "Interior Cockpit", desc: "Mount dashboard, steering column, center console, and bucket seats.", parts: ["DASH-01", "STEER-01", "CONSOLE-01", "SEAT-L-BASE", "SEAT-L-BACK", "SEAT-R-BASE", "SEAT-R-BACK"] },
    { num: 5, title: "Front Clip & Hood", desc: "Attach radiator grille, front fenders, hood deck, and front bumper.", parts: ["GRILL-01", "BMPR-F", "HOOD-01", "FEND-FL", "FEND-FR"] },
    { num: 6, title: "Cabin Canopy & Roof", desc: "Seat windshield frame, main roof deck, and rear window louvers.", parts: ["WINDSHIELD-01", "ROOF-01", "REAR-WINDOW-01", "LOUVER-01", "LOUVER-02", "LOUVER-03"] },
    { num: 7, title: "Rear Bodywork & Trunk", desc: "Install quarter panels, trunk decklid, taillight panel, and rear bumper.", parts: ["QTR-RL", "QTR-RR", "DOOR-L", "DOOR-R", "TRUNK-01", "TAIL-01", "BMPR-R"] },
    { num: 8, title: "Axles & Circular Layered Wheels", desc: "Mount cross-axle beams and assemble 4 true-circular five-layer wheel stacks.", parts: ["AXLE-F", "AXLE-R", "W-FL-L1", "W-FL-ROTOR", "W-FL-L2", "W-FL-FACE", "W-FL-CAP", "W-FR-L1", "W-FR-ROTOR", "W-FR-L2", "W-FR-FACE", "W-FR-CAP", "W-RL-L1", "W-RL-ROTOR", "W-RL-L2", "W-RL-FACE", "W-RL-CAP", "W-RR-L1", "W-RR-ROTOR", "W-RR-L2", "W-RR-FACE", "W-RR-CAP"] }
  ],
  manufacturingSheets: [
    {
      sheetNum: 1,
      name: "car_chassis_sheet.svg",
      desc: "Baseplate, main spine, and longitudinal frames.",
      sheetW: 600,
      sheetH: 400,
      layout: {
        "CHASSIS-01": { x: 140, y: 60, r: 0 },
        "SPINE-01": { x: 410, y: 25, r: 0 },
        "FRAME-L": { x: 135, y: 130, r: 0 },
        "FRAME-R": { x: 395, y: 130, r: 0 }
      }
    }
  ],
  parts: [
    // -------------------------------------------------------------
    // 1. CHASSIS & LADDER FRAME (Step 1)
    // -------------------------------------------------------------
    {
      id: "CHASSIS-01",
      fileName: "CHASSIS-01.svg",
      name: "Chassis Belly Pan",
      category: "Foundation",
      color: "#eddcd2",
      step: 1,
      width: 250,
      length: 88,
      sheet: 1,
      fileSizeKB: "4.8 KB",
      assembledPos: [0, 8, 0],
      assembledRot: [-1.5707963267948966, 0, 0],
      explodeVec: [0, -45, 0],
      connections: ["SPINE-01", "FRAME-L", "FRAME-R"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-115, -85, -55, -20, 15, 50, 85, 115];
        const cutouts = [];
        bXs.forEach(x => {
          cutouts.push({ x: x, y: 0, w: 12, h: sw });
          cutouts.push({ x: x, y: -22, w: 10, h: sw });
          cutouts.push({ x: x, y: 22, w: 10, h: sw });
        });
        return {
          outline: [
            [-125, -32], [-100, -32], [-95, -40], [-50, -40], [-45, -32],
            [45, -32], [50, -40], [95, -40], [100, -32], [125, -32],
            [125, 32], [100, 32], [95, 40], [50, 40], [45, 32],
            [-45, 32], [-50, 40], [-95, 40], [-100, 32], [-125, 32]
          ],
          cutouts: cutouts,
          engravings: [
            { type: "line", x1: -120, y1: 0, x2: 120, y2: 0 },
            { type: "rect", x: -35, y: -16, w: 70, h: 32 }
          ]
        };
      }
    },
    {
      id: "SPINE-01",
      fileName: "SPINE-01.svg",
      name: "Longitudinal Center Spine",
      category: "Structural",
      color: "#b07d62",
      step: 1,
      width: 230,
      length: 20,
      sheet: 1,
      fileSizeKB: "3.2 KB",
      assembledPos: [0, 15, 0],
      assembledRot: [0, 0, 0],
      explodeVec: [0, -25, 0],
      connections: ["CHASSIS-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-115, -85, -55, -20, 15, 50, 85, 115];
        return {
          outline: [
            [-115, -9],
            [-95, -9], [-95, -9 - t], [-75, -9 - t], [-75, -9],
            [-10, -9], [-10, -9 - t], [10, -10 - t], [10, -9],
            [75, -9], [75, -9 - t], [95, -9 - t], [95, -9],
            [115, -9], [115, 9], [-115, 9]
          ],
          cutouts: bXs.map(x => ({ x: x, y: 2, w: sw, h: 9 })),
          engravings: []
        };
      }
    },
    {
      id: "FRAME-L",
      fileName: "FRAME-L.svg",
      name: "Left Ladder Rail",
      category: "Structural",
      color: "#8c6239",
      step: 1,
      width: 230,
      length: 15,
      sheet: 1,
      fileSizeKB: "2.3 KB",
      assembledPos: [0, 12, -22],
      assembledRot: [0, 0, 0],
      explodeVec: [0, -15, -15],
      connections: ["CHASSIS-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-115, -85, -55, -20, 15, 50, 85, 115];
        return {
          outline: [
            [-115, -6.5],
            [-80, -6.5], [-80, -6.5 - t], [-60, -6.5 - t], [-60, -6.5],
            [60, -6.5], [60, -6.5 - t], [80, -6.5 - t], [80, -6.5],
            [115, -6.5], [115, 6.5], [-115, 6.5]
          ],
          cutouts: bXs.map(x => ({ x: x, y: 1.5, w: sw, h: 7 })),
          engravings: [{ type: "line", x1: -110, y1: 0, x2: 110, y2: 0 }]
        };
      }
    },
    {
      id: "FRAME-R",
      fileName: "FRAME-R.svg",
      name: "Right Ladder Rail",
      category: "Structural",
      color: "#8c6239",
      step: 1,
      width: 230,
      length: 15,
      sheet: 1,
      fileSizeKB: "2.3 KB",
      assembledPos: [0, 12, 22],
      assembledRot: [0, 0, 0],
      explodeVec: [0, -15, 15],
      connections: ["CHASSIS-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-115, -85, -55, -20, 15, 50, 85, 115];
        return {
          outline: [
            [-115, -6.5],
            [-80, -6.5], [-80, -6.5 - t], [-60, -6.5 - t], [-60, -6.5],
            [60, -6.5], [60, -6.5 - t], [80, -6.5 - t], [80, -6.5],
            [115, -6.5], [115, 6.5], [-115, 6.5]
          ],
          cutouts: bXs.map(x => ({ x: x, y: 1.5, w: sw, h: 7 })),
          engravings: [{ type: "line", x1: -110, y1: 0, x2: 110, y2: 0 }]
        };
      }
    },

    // -------------------------------------------------------------
    // 2. FORM BULKHEADS (Step 2)
    // -------------------------------------------------------------
    {
      id: "BLK-01",
      fileName: "BLK-01.svg",
      name: "Front Grille Core Bulkhead",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 70,
      length: 26,
      sheet: 1,
      fileSizeKB: "2.0 KB",
      assembledPos: [-115, 21, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-35, -13],
            [-16, -13], [-16, -13 - t], [16, -13 - t], [16, -13],
            [35, -13], [35, 6], [30, 13], [-30, 13], [-35, 6]
          ],
          cutouts: [
            { x: 0, y: -7, w: sw, h: 10 },
            { x: -22, y: -9, w: sw, h: 7 }, { x: 22, y: -9, w: sw, h: 7 },
            { x: -32, y: 0, w: 5, h: sw }, { x: 32, y: 0, w: 5, h: sw }
          ],
          engravings: [{ type: "circle", x: 0, y: 6, r: 3 }]
        };
      }
    },
    {
      id: "BLK-02",
      fileName: "BLK-02.svg",
      name: "Radiator & Front Suspension Station",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 74,
      length: 30,
      sheet: 1,
      fileSizeKB: "2.1 KB",
      assembledPos: [-85, 23, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-37, -15],
            [-17, -15], [-17, -15 - t], [17, -15 - t], [17, -15],
            [37, -15], [37, 7], [33, 15], [-33, 15], [-37, 7]
          ],
          cutouts: [
            { x: 0, y: -8, w: sw, h: 11 },
            { x: -22, y: -10, w: sw, h: 7 }, { x: 22, y: -10, w: sw, h: 7 },
            { x: -34, y: 0, w: 5, h: sw }, { x: 34, y: 0, w: 5, h: sw },
            { x: -32, y: 8, w: sw, h: 6 }, { x: 32, y: 8, w: sw, h: 6 }
          ],
          engravings: []
        };
      }
    },
    {
      id: "BLK-03",
      fileName: "BLK-03.svg",
      name: "Front Firewall Bulkhead",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 78,
      length: 38,
      sheet: 1,
      fileSizeKB: "2.2 KB",
      assembledPos: [-55, 27, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-39, -19],
            [-18, -19], [-18, -19 - t], [18, -19 - t], [18, -19],
            [39, -19], [39, 9], [34, 19], [-34, 19], [-39, 9]
          ],
          cutouts: [
            { x: 0, y: -10, w: sw, h: 13 },
            { x: -22, y: -12, w: sw, h: 7 }, { x: 22, y: -12, w: sw, h: 7 },
            { x: -36, y: 0, w: 5, h: sw }, { x: 36, y: 0, w: 5, h: sw },
            { x: -33, y: 10, w: sw, h: 6 }, { x: 33, y: 10, w: sw, h: 6 }
          ],
          engravings: []
        };
      }
    },
    {
      id: "BLK-04",
      fileName: "BLK-04.svg",
      name: "Instrument Panel Bulkhead",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 80,
      length: 40,
      sheet: 1,
      fileSizeKB: "2.2 KB",
      assembledPos: [-20, 28, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-40, -20],
            [-19, -20], [-19, -20 - t], [19, -20 - t], [19, -20],
            [40, -20], [40, 10], [35, 20], [-35, 20], [-40, 10]
          ],
          cutouts: [
            { x: 0, y: -11, w: sw, h: 13 },
            { x: -22, y: -13, w: sw, h: 7 }, { x: 22, y: -13, w: sw, h: 7 },
            { x: -37, y: 0, w: 5, h: sw }, { x: 37, y: 0, w: 5, h: sw }
          ],
          engravings: []
        };
      }
    },
    {
      id: "BLK-05",
      fileName: "BLK-05.svg",
      name: "Mid-Cabin B-Pillar Bulkhead",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 80,
      length: 40,
      sheet: 1,
      fileSizeKB: "2.2 KB",
      assembledPos: [15, 28, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-40, -20],
            [-19, -20], [-19, -20 - t], [19, -20 - t], [19, -20],
            [40, -20], [40, 10], [35, 20], [-35, 20], [-40, 10]
          ],
          cutouts: [
            { x: 0, y: -11, w: sw, h: 13 },
            { x: -22, y: -13, w: sw, h: 7 }, { x: 22, y: -13, w: sw, h: 7 },
            { x: -37, y: 0, w: 5, h: sw }, { x: 37, y: 0, w: 5, h: sw }
          ],
          engravings: []
        };
      }
    },
    {
      id: "BLK-06",
      fileName: "BLK-06.svg",
      name: "Rear Seat & Fastback Transition",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 78,
      length: 38,
      sheet: 1,
      fileSizeKB: "2.2 KB",
      assembledPos: [50, 27, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-39, -19],
            [-18, -19], [-18, -19 - t], [18, -19 - t], [18, -19],
            [39, -19], [39, 9], [34, 19], [-34, 19], [-39, 9]
          ],
          cutouts: [
            { x: 0, y: -10, w: sw, h: 13 },
            { x: -22, y: -12, w: sw, h: 7 }, { x: 22, y: -12, w: sw, h: 7 },
            { x: -36, y: 0, w: 5, h: sw }, { x: 36, y: 0, w: 5, h: sw },
            { x: -33, y: 10, w: sw, h: 6 }, { x: 33, y: 10, w: sw, h: 6 }
          ],
          engravings: []
        };
      }
    },
    {
      id: "BLK-07",
      fileName: "BLK-07.svg",
      name: "Rear Axle Arch Bulkhead",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 74,
      length: 32,
      sheet: 1,
      fileSizeKB: "2.1 KB",
      assembledPos: [85, 24, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-37, -16],
            [-17, -16], [-17, -16 - t], [17, -16 - t], [17, -16],
            [37, -16], [37, 7], [33, 16], [-33, 16], [-37, 7]
          ],
          cutouts: [
            { x: 0, y: -9, w: sw, h: 11 },
            { x: -22, y: -11, w: sw, h: 7 }, { x: 22, y: -11, w: sw, h: 7 },
            { x: -34, y: 0, w: 5, h: sw }, { x: 34, y: 0, w: 5, h: sw },
            { x: -32, y: 8, w: sw, h: 6 }, { x: 32, y: 8, w: sw, h: 6 }
          ],
          engravings: []
        };
      }
    },
    {
      id: "BLK-08",
      fileName: "BLK-08.svg",
      name: "Rear Trunk Valance Bulkhead",
      category: "Structural",
      color: "#d4a373",
      step: 2,
      width: 70,
      length: 26,
      sheet: 1,
      fileSizeKB: "2.0 KB",
      assembledPos: [115, 21, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [0, 15, 0],
      connections: ["CHASSIS-01", "SPINE-01"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-35, -13],
            [-16, -13], [-16, -13 - t], [16, -13 - t], [16, -13],
            [35, -13], [35, 6], [31, 13], [-31, 13], [-35, 6]
          ],
          cutouts: [
            { x: 0, y: -7, w: sw, h: 10 },
            { x: -22, y: -9, w: sw, h: 7 }, { x: 22, y: -9, w: sw, h: 7 },
            { x: -32, y: 0, w: 5, h: sw }, { x: 32, y: 0, w: 5, h: sw }
          ],
          engravings: []
        };
      }
    },

    // -------------------------------------------------------------
    // 3. FLANK STRINGERS & WHEELHOUSE BRACES (Step 3)
    // -------------------------------------------------------------
    {
      id: "SILL-L",
      fileName: "SILL-L.svg",
      name: "Left Lower Sill Stringer",
      category: "Structural",
      color: "#c68b59",
      step: 3,
      width: 230,
      length: 8,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [0, 15, -38],
      assembledRot: [1.5707963267948966, 0, 0],
      explodeVec: [0, 0, -18],
      connections: ["BLK-01", "BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07", "BLK-08"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-115, -85, -55, -20, 15, 50, 85, 115];
        return {
          outline: [[-115, -4], [115, -4], [115, 4], [-115, 4]],
          cutouts: bXs.map(x => ({ x: x, y: 0, w: sw, h: 4 })),
          engravings: [{ type: "line", x1: -110, y1: 0, x2: 110, y2: 0 }]
        };
      }
    },
    {
      id: "SILL-R",
      fileName: "SILL-R.svg",
      name: "Right Lower Sill Stringer",
      category: "Structural",
      color: "#c68b59",
      step: 3,
      width: 230,
      length: 8,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [0, 15, 38],
      assembledRot: [1.5707963267948966, 0, 0],
      explodeVec: [0, 0, 18],
      connections: ["BLK-01", "BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07", "BLK-08"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-115, -85, -55, -20, 15, 50, 85, 115];
        return {
          outline: [[-115, -4], [115, -4], [115, 4], [-115, 4]],
          cutouts: bXs.map(x => ({ x: x, y: 0, w: sw, h: 4 })),
          engravings: [{ type: "line", x1: -110, y1: 0, x2: 110, y2: 0 }]
        };
      }
    },
    {
      id: "WAIST-L",
      fileName: "WAIST-L.svg",
      name: "Left Upper Waist Stringer",
      category: "Structural",
      color: "#c68b59",
      step: 3,
      width: 210,
      length: 8,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [0, 28, -36],
      assembledRot: [1.5707963267948966, 0, 0],
      explodeVec: [0, 0, -22],
      connections: ["BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-85, -55, -20, 15, 50, 85];
        return {
          outline: [[-105, -4], [105, -4], [105, 4], [-105, 4]],
          cutouts: bXs.map(x => ({ x: x, y: 0, w: sw, h: 4 })),
          engravings: [{ type: "line", x1: -100, y1: 0, x2: 100, y2: 0 }]
        };
      }
    },
    {
      id: "WAIST-R",
      fileName: "WAIST-R.svg",
      name: "Right Upper Waist Stringer",
      category: "Structural",
      color: "#c68b59",
      step: 3,
      width: 210,
      length: 8,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [0, 28, 36],
      assembledRot: [1.5707963267948966, 0, 0],
      explodeVec: [0, 0, 22],
      connections: ["BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        const bXs = [-85, -55, -20, 15, 50, 85];
        return {
          outline: [[-105, -4], [105, -4], [105, 4], [-105, 4]],
          cutouts: bXs.map(x => ({ x: x, y: 0, w: sw, h: 4 })),
          engravings: [{ type: "line", x1: -100, y1: 0, x2: 100, y2: 0 }]
        };
      }
    },
    {
      id: "ARCH-BRACE-FL",
      fileName: "ARCH-BRACE-FL.svg",
      name: "Front-Left Wheelhouse Arch Support",
      category: "Support",
      color: "#b07d62",
      step: 3,
      width: 32,
      length: 12,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [-70, 31, -34],
      assembledRot: [0, 0, 0],
      explodeVec: [-10, 15, -15],
      connections: ["BLK-02", "BLK-03"],
      generate2D: (t) => ({
        outline: [
          [-16, -6],
          [-16, -6 - t], [-11, -6 - t], [-11, -6],
          [11, -6], [11, -6 - t], [16, -6 - t], [16, -6],
          [16, 6], [-16, 6]
        ],
        cutouts: [{ x: 0, y: -2, w: 20, h: 6, arched: true }],
        engravings: [{ type: "line", x1: -14, y1: 3, x2: 14, y2: 3 }]
      })
    },
    {
      id: "ARCH-BRACE-FR",
      fileName: "ARCH-BRACE-FR.svg",
      name: "Front-Right Wheelhouse Arch Support",
      category: "Support",
      color: "#b07d62",
      step: 3,
      width: 32,
      length: 12,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [-70, 31, 34],
      assembledRot: [0, 0, 0],
      explodeVec: [-10, 15, 15],
      connections: ["BLK-02", "BLK-03"],
      generate2D: (t) => ({
        outline: [
          [-16, -6],
          [-16, -6 - t], [-11, -6 - t], [-11, -6],
          [11, -6], [11, -6 - t], [16, -6 - t], [16, -6],
          [16, 6], [-16, 6]
        ],
        cutouts: [{ x: 0, y: -2, w: 20, h: 6, arched: true }],
        engravings: [{ type: "line", x1: -14, y1: 3, x2: 14, y2: 3 }]
      })
    },
    {
      id: "ARCH-BRACE-RL",
      fileName: "ARCH-BRACE-RL.svg",
      name: "Rear-Left Wheelhouse Arch Support",
      category: "Support",
      color: "#b07d62",
      step: 3,
      width: 32,
      length: 12,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [67, 31, -34],
      assembledRot: [0, 0, 0],
      explodeVec: [10, 15, -15],
      connections: ["BLK-06", "BLK-07"],
      generate2D: (t) => ({
        outline: [
          [-16, -6],
          [-16, -6 - t], [-11, -6 - t], [-11, -6],
          [11, -6], [11, -6 - t], [16, -6 - t], [16, -6],
          [16, 6], [-16, 6]
        ],
        cutouts: [{ x: 0, y: -2, w: 20, h: 6, arched: true }],
        engravings: [{ type: "line", x1: -14, y1: 3, x2: 14, y2: 3 }]
      })
    },
    {
      id: "ARCH-BRACE-RR",
      fileName: "ARCH-BRACE-RR.svg",
      name: "Rear-Right Wheelhouse Arch Support",
      category: "Support",
      color: "#b07d62",
      step: 3,
      width: 32,
      length: 12,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [67, 31, 34],
      assembledRot: [0, 0, 0],
      explodeVec: [10, 15, 15],
      connections: ["BLK-06", "BLK-07"],
      generate2D: (t) => ({
        outline: [
          [-16, -6],
          [-16, -6 - t], [-11, -6 - t], [-11, -6],
          [11, -6], [11, -6 - t], [16, -6 - t], [16, -6],
          [16, 6], [-16, 6]
        ],
        cutouts: [{ x: 0, y: -2, w: 20, h: 6, arched: true }],
        engravings: [{ type: "line", x1: -14, y1: 3, x2: 14, y2: 3 }]
      })
    },

    // -------------------------------------------------------------
    // 4. CABIN INTERIOR (Step 4)
    // -------------------------------------------------------------
    {
      id: "DASH-01",
      fileName: "DASH-01.svg",
      name: "Driver Instrument Dashboard",
      category: "Details",
      color: "#343a40",
      step: 4,
      width: 72,
      length: 16,
      sheet: 1,
      fileSizeKB: "1.7 KB",
      assembledPos: [-20, 30, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [-15, 10, 0],
      connections: ["BLK-04"],
      generate2D: () => ({
        outline: [
          [-36, -8], [36, -8],
          [36, 4], [24, 8], [-24, 8], [-36, 4]
        ],
        cutouts: [
          { x: -16, y: 0, w: 9, h: 9 },
          { x: -5, y: 0, w: 9, h: 9 },
          { x: 16, y: -2, w: 16, h: 7 }
        ],
        engravings: [
          { type: "circle", x: -16, y: 0, r: 3.5 },
          { type: "circle", x: -5, y: 0, r: 3.5 }
        ]
      })
    },
    {
      id: "STEER-01",
      fileName: "STEER-01.svg",
      name: "Vintage Steering Wheel",
      category: "Details",
      color: "#c68b59",
      step: 4,
      width: 15,
      length: 15,
      sheet: 1,
      fileSizeKB: "1.2 KB",
      assembledPos: [-12, 28, -16],
      assembledRot: [0, 1.5707963267948966, -0.3],
      explodeVec: [-10, 5, 0],
      connections: ["DASH-01"],
      generate2D: () => ({
        outline: [[-7.5, -7.5], [7.5, -7.5], [7.5, 7.5], [-7.5, 7.5]],
        cutouts: [{ x: 0, y: 0, w: 11, h: 11 }],
        engravings: [
          { type: "circle", x: 0, y: 0, r: 6.5 },
          { type: "line", x1: 0, y1: -6.5, x2: 0, y2: 6.5 },
          { type: "line", x1: -6.5, y1: 0, x2: 6.5, y2: 0 }
        ]
      })
    },
    {
      id: "CONSOLE-01",
      fileName: "CONSOLE-01.svg",
      name: "Transmission Tunnel Console",
      category: "Details",
      color: "#8c6239",
      step: 4,
      width: 80,
      length: 10,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [-5, 17, 0],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 12, 0],
      connections: ["CHASSIS-01"],
      generate2D: () => ({
        outline: [[-40, -5], [40, -5], [40, 5], [-40, 5]],
        cutouts: [
          { x: -12, y: 0, w: 4, h: 4 },
          { x: 16, y: 0, w: 5, h: 6 }
        ],
        engravings: [{ type: "rect", x: -35, y: -3.5, w: 70, h: 7 }]
      })
    },
    {
      id: "SEAT-L-BASE",
      fileName: "SEAT-L-BASE.svg",
      name: "Driver Bucket Cushion Base",
      category: "Details",
      color: "#8c6239",
      step: 4,
      width: 20,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.2 KB",
      assembledPos: [-5, 12, -16],
      assembledRot: [-1.5707963267948966, 0, 0],
      explodeVec: [0, 10, 0],
      connections: ["CHASSIS-01"],
      generate2D: (t) => ({
        outline: [[-10, -10], [10, -10], [10, 10], [-10, 10]],
        cutouts: [{ x: 7, y: 0, w: t, h: 12 }],
        engravings: [{ type: "rect", x: -7, y: -7, w: 14, h: 14 }]
      })
    },
    {
      id: "SEAT-L-BACK",
      fileName: "SEAT-L-BACK.svg",
      name: "Driver Bucket Seat Backrest",
      category: "Details",
      color: "#8c6239",
      step: 4,
      width: 18,
      length: 24,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [3, 23, -16],
      assembledRot: [0, 1.5707963267948966, 0.2],
      explodeVec: [5, 12, 0],
      connections: ["SEAT-L-BASE"],
      generate2D: (t) => ({
        outline: [
          [-9, -12],
          [-5, -12], [-5, -12 - t], [5, -12 - t], [5, -12],
          [9, -12], [8, 12], [-8, 12]
        ],
        cutouts: [],
        engravings: [
          { type: "line", x1: -3.5, y1: -9, x2: -3.5, y2: 9 },
          { type: "line", x1: 0, y1: -9, x2: 0, y2: 9 },
          { type: "line", x1: 3.5, y1: -9, x2: 3.5, y2: 9 }
        ]
      })
    },
    {
      id: "SEAT-R-BASE",
      fileName: "SEAT-R-BASE.svg",
      name: "Passenger Bucket Cushion Base",
      category: "Details",
      color: "#8c6239",
      step: 4,
      width: 20,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.2 KB",
      assembledPos: [-5, 12, 16],
      assembledRot: [-1.5707963267948966, 0, 0],
      explodeVec: [0, 10, 0],
      connections: ["CHASSIS-01"],
      generate2D: (t) => ({
        outline: [[-10, -10], [10, -10], [10, 10], [-10, 10]],
        cutouts: [{ x: 7, y: 0, w: t, h: 12 }],
        engravings: [{ type: "rect", x: -7, y: -7, w: 14, h: 14 }]
      })
    },
    {
      id: "SEAT-R-BACK",
      fileName: "SEAT-R-BACK.svg",
      name: "Passenger Bucket Seat Backrest",
      category: "Details",
      color: "#8c6239",
      step: 4,
      width: 18,
      length: 24,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [3, 23, 16],
      assembledRot: [0, 1.5707963267948966, 0.2],
      explodeVec: [5, 12, 0],
      connections: ["SEAT-R-BASE"],
      generate2D: (t) => ({
        outline: [
          [-9, -12],
          [-5, -12], [-5, -12 - t], [5, -12 - t], [5, -12],
          [9, -12], [8, 12], [-8, 12]
        ],
        cutouts: [],
        engravings: [
          { type: "line", x1: -3.5, y1: -9, x2: -3.5, y2: 9 },
          { type: "line", x1: 0, y1: -9, x2: 0, y2: 9 },
          { type: "line", x1: 3.5, y1: -9, x2: 3.5, y2: 9 }
        ]
      })
    },

    // -------------------------------------------------------------
    // 5. FRONT CLIP & HOOD (Step 5)
    // -------------------------------------------------------------
    {
      id: "GRILL-01",
      fileName: "GRILL-01.svg",
      name: "Front Radiator Grille Screen",
      category: "Details",
      color: "#212529",
      step: 5,
      width: 64,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [-116, 21, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [-20, 0, 0],
      connections: ["BLK-01"],
      generate2D: () => ({
        outline: [[-32, -10], [32, -10], [32, 10], [-32, 10]],
        cutouts: [
          { x: -22, y: 0, w: 7, h: 7 },
          { x: 22, y: 0, w: 7, h: 7 }
        ],
        engravings: [
          { type: "rect", x: -14, y: -5, w: 28, h: 10 },
          { type: "circle", x: 0, y: 0, r: 2.5 }
        ]
      })
    },
    {
      id: "BMPR-F",
      fileName: "BMPR-F.svg",
      name: "Front Chrome Blade Bumper",
      category: "Details",
      color: "#ced4da",
      step: 5,
      width: 72,
      length: 7,
      sheet: 1,
      fileSizeKB: "1.1 KB",
      assembledPos: [-120, 13, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [-18, 0, 0],
      connections: ["BLK-01"],
      generate2D: () => ({
        outline: [[-36, -3.5], [36, -3.5], [34, 3.5], [-34, 3.5]],
        cutouts: [],
        engravings: [{ type: "line", x1: -32, y1: 0, x2: 32, y2: 0 }]
      })
    },
    {
      id: "HOOD-01",
      fileName: "HOOD-01.svg",
      name: "Front Louvered Hood Deck",
      category: "Surface",
      color: "#d4a373",
      step: 5,
      width: 68,
      length: 60,
      sheet: 1,
      fileSizeKB: "2.3 KB",
      assembledPos: [-70, 31, 0],
      assembledRot: [-1.5707963267948966, 0, 0],
      explodeVec: [0, 20, 0],
      connections: ["BLK-02", "BLK-03"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [
            [-34, -30], [34, -30],
            [32, 30], [-32, 30]
          ],
          cutouts: [
            { x: -12, y: 0, w: 6, h: 20 },
            { x: 12, y: 0, w: 6, h: 20 },
            { x: -18, y: 26, w: sw, h: 5 },
            { x: 18, y: 26, w: sw, h: 5 }
          ],
          engravings: [
            { type: "rect", x: -28, y: -26, w: 56, h: 52 },
            { type: "line", x1: 0, y1: -28, x2: 0, y2: 28 }
          ]
        };
      }
    },
    {
      id: "FEND-FL",
      fileName: "FEND-FL.svg",
      name: "Front-Left Side Fender",
      category: "Surface",
      color: "#d4a373",
      step: 5,
      width: 74,
      length: 24,
      sheet: 1,
      fileSizeKB: "1.9 KB",
      assembledPos: [-80, 21, -38],
      assembledRot: [0, 3.141592653589793, 0],
      explodeVec: [0, 0, -20],
      connections: ["BLK-01", "BLK-03"],
      generate2D: () => ({
        outline: [
          [-37, -12], [37, -12],
          [37, 12], [-32, 12], [-37, 7]
        ],
        cutouts: [{ x: 5, y: -6, w: 32, h: 12, arched: true }],
        engravings: [{ type: "line", x1: -35, y1: 5, x2: 35, y2: 5 }]
      })
    },
    {
      id: "FEND-FR",
      fileName: "FEND-FR.svg",
      name: "Front-Right Side Fender",
      category: "Surface",
      color: "#d4a373",
      step: 5,
      width: 74,
      length: 24,
      sheet: 1,
      fileSizeKB: "1.9 KB",
      assembledPos: [-80, 21, 38],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 20],
      connections: ["BLK-01", "BLK-03"],
      generate2D: () => ({
        outline: [
          [-37, -12], [37, -12],
          [37, 12], [-32, 12], [-37, 7]
        ],
        cutouts: [{ x: 5, y: -6, w: 32, h: 12, arched: true }],
        engravings: [{ type: "line", x1: -35, y1: 5, x2: 35, y2: 5 }]
      })
    },

    // -------------------------------------------------------------
    // 6. CANOPY & ROOF LOUVERS (Step 6)
    // -------------------------------------------------------------
    {
      id: "WINDSHIELD-01",
      fileName: "WINDSHIELD-01.svg",
      name: "Raked Windshield A-Pillar Frame",
      category: "Structural",
      color: "#eddcd2",
      step: 6,
      width: 70,
      length: 28,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [-35, 35, 0],
      assembledRot: [0.65, 1.5707963267948966, 0],
      explodeVec: [-12, 12, 0],
      connections: ["BLK-03", "BLK-04"],
      generate2D: () => ({
        outline: [
          [-35, -14], [35, -14],
          [30, 14], [-30, 14]
        ],
        cutouts: [{ x: 0, y: 0, w: 54, h: 20 }],
        engravings: [{ type: "rect", x: -32, y: -12, w: 64, h: 24 }]
      })
    },
    {
      id: "ROOF-01",
      fileName: "ROOF-01.svg",
      name: "Cabin Roof Turret Skin",
      category: "Surface",
      color: "#b07d62",
      step: 6,
      width: 62,
      length: 50,
      sheet: 1,
      fileSizeKB: "2.0 KB",
      assembledPos: [0, 46, 0],
      assembledRot: [-1.5707963267948966, 0, 0],
      explodeVec: [0, 25, 0],
      connections: ["BLK-04", "BLK-05"],
      generate2D: (t, kerf, clr) => {
        const sw = t + clr;
        return {
          outline: [[-31, -25], [31, -25], [31, 25], [-31, 25]],
          cutouts: [
            { x: -18, y: -16, w: 7, h: sw },
            { x: 18, y: -16, w: 7, h: sw },
            { x: -18, y: 16, w: 7, h: sw },
            { x: 18, y: 16, w: 7, h: sw }
          ],
          engravings: [
            { type: "line", x1: -26, y1: -22, x2: 26, y2: -22 },
            { type: "line", x1: -26, y1: 22, x2: 26, y2: 22 }
          ]
        };
      }
    },
    {
      id: "REAR-WINDOW-01",
      fileName: "REAR-WINDOW-01.svg",
      name: "Fastback Rear Backlight Frame",
      category: "Structural",
      color: "#eddcd2",
      step: 6,
      width: 66,
      length: 40,
      sheet: 1,
      fileSizeKB: "1.9 KB",
      assembledPos: [42, 38, 0],
      assembledRot: [-0.45, 1.5707963267948966, 0],
      explodeVec: [12, 15, 0],
      connections: ["BLK-05", "BLK-06"],
      generate2D: () => ({
        outline: [
          [-33, -20], [33, -20],
          [28, 20], [-28, 20]
        ],
        cutouts: [{ x: 0, y: 0, w: 50, h: 28 }],
        engravings: [{ type: "rect", x: -30, y: -17, w: 60, h: 34 }]
      })
    },
    {
      id: "LOUVER-01",
      fileName: "LOUVER-01.svg",
      name: "Rear Window Sun Slat 1",
      category: "Details",
      color: "#212529",
      step: 6,
      width: 52,
      length: 7,
      sheet: 1,
      fileSizeKB: "1.0 KB",
      assembledPos: [32, 42, 0],
      assembledRot: [-0.42, 0, 0],
      explodeVec: [8, 16, 0],
      connections: ["REAR-WINDOW-01"],
      generate2D: () => ({
        outline: [[-26, -3.5], [26, -3.5], [26, 3.5], [-26, 3.5]],
        cutouts: [],
        engravings: [{ type: "line", x1: -22, y1: 0, x2: 22, y2: 0 }]
      })
    },
    {
      id: "LOUVER-02",
      fileName: "LOUVER-02.svg",
      name: "Rear Window Sun Slat 2",
      category: "Details",
      color: "#212529",
      step: 6,
      width: 50,
      length: 7,
      sheet: 1,
      fileSizeKB: "1.0 KB",
      assembledPos: [40, 39, 0],
      assembledRot: [-0.42, 0, 0],
      explodeVec: [8, 16, 0],
      connections: ["REAR-WINDOW-01"],
      generate2D: () => ({
        outline: [[-25, -3.5], [25, -3.5], [25, 3.5], [-25, 3.5]],
        cutouts: [],
        engravings: [{ type: "line", x1: -21, y1: 0, x2: 21, y2: 0 }]
      })
    },
    {
      id: "LOUVER-03",
      fileName: "LOUVER-03.svg",
      name: "Rear Window Sun Slat 3",
      category: "Details",
      color: "#212529",
      step: 6,
      width: 48,
      length: 7,
      sheet: 1,
      fileSizeKB: "1.0 KB",
      assembledPos: [48, 36, 0],
      assembledRot: [-0.42, 0, 0],
      explodeVec: [8, 16, 0],
      connections: ["REAR-WINDOW-01"],
      generate2D: () => ({
        outline: [[-24, -3.5], [24, -3.5], [24, 3.5], [-24, 3.5]],
        cutouts: [],
        engravings: [{ type: "line", x1: -20, y1: 0, x2: 20, y2: 0 }]
      })
    },

    // -------------------------------------------------------------
    // 7. REAR BODYWORK & TRUNK (Step 7)
    // -------------------------------------------------------------
    {
      id: "QTR-RL",
      fileName: "QTR-RL.svg",
      name: "Left Rear Quarter Panel",
      category: "Surface",
      color: "#d4a373",
      step: 7,
      width: 85,
      length: 25,
      sheet: 1,
      fileSizeKB: "2.1 KB",
      assembledPos: [70, 21, -38],
      assembledRot: [0, 3.141592653589793, 0],
      explodeVec: [0, 0, -20],
      connections: ["BLK-06", "BLK-08"],
      generate2D: () => ({
        outline: [
          [-42.5, -12.5], [42.5, -12.5],
          [42.5, 7], [38, 12.5], [-42.5, 12.5]
        ],
        cutouts: [
          { x: 0, y: -6, w: 34, h: 13, arched: true },
          { x: -26, y: 3, w: 5, h: 10 }
        ],
        engravings: [{ type: "line", x1: -40, y1: 6, x2: 40, y2: 6 }]
      })
    },
    {
      id: "QTR-RR",
      fileName: "QTR-RR.svg",
      name: "Right Rear Quarter Panel",
      category: "Surface",
      color: "#d4a373",
      step: 7,
      width: 85,
      length: 25,
      sheet: 1,
      fileSizeKB: "2.1 KB",
      assembledPos: [70, 21, 38],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 20],
      connections: ["BLK-06", "BLK-08"],
      generate2D: () => ({
        outline: [
          [-42.5, -12.5], [42.5, -12.5],
          [42.5, 7], [38, 12.5], [-42.5, 12.5]
        ],
        cutouts: [
          { x: 0, y: -6, w: 34, h: 13, arched: true },
          { x: -26, y: 3, w: 5, h: 10 }
        ],
        engravings: [{ type: "line", x1: -40, y1: 6, x2: 40, y2: 6 }]
      })
    },
    {
      id: "DOOR-L",
      fileName: "DOOR-L.svg",
      name: "Left Cockpit Door Panel",
      category: "Surface",
      color: "#c68b59",
      step: 7,
      width: 55,
      length: 22,
      sheet: 1,
      fileSizeKB: "1.6 KB",
      assembledPos: [-5, 19, -39],
      assembledRot: [0, 3.141592653589793, 0],
      explodeVec: [0, 0, -18],
      connections: ["SILL-L", "WAIST-L"],
      generate2D: () => ({
        outline: [[-27.5, -11], [27.5, -11], [27.5, 11], [-27.5, 11]],
        cutouts: [{ x: 16, y: 4, w: 5, h: 3 }],
        engravings: [
          { type: "line", x1: -25, y1: 0, x2: 25, y2: 0 },
          { type: "rect", x: -25, y: -9, w: 50, h: 18 }
        ]
      })
    },
    {
      id: "DOOR-R",
      fileName: "DOOR-R.svg",
      name: "Right Cockpit Door Panel",
      category: "Surface",
      color: "#c68b59",
      step: 7,
      width: 55,
      length: 22,
      sheet: 1,
      fileSizeKB: "1.6 KB",
      assembledPos: [-5, 19, 39],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 18],
      connections: ["SILL-R", "WAIST-R"],
      generate2D: () => ({
        outline: [[-27.5, -11], [27.5, -11], [27.5, 11], [-27.5, 11]],
        cutouts: [{ x: 16, y: 4, w: 5, h: 3 }],
        engravings: [
          { type: "line", x1: -25, y1: 0, x2: 25, y2: 0 },
          { type: "rect", x: -25, y: -9, w: 50, h: 18 }
        ]
      })
    },
    {
      id: "TRUNK-01",
      fileName: "TRUNK-01.svg",
      name: "Rear Trunk Decklid",
      category: "Surface",
      color: "#d4a373",
      step: 7,
      width: 58,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.5 KB",
      assembledPos: [95, 29, 0],
      assembledRot: [-1.4707963267948965, 0, 0],
      explodeVec: [12, 16, 0],
      connections: ["BLK-07", "BLK-08"],
      generate2D: () => ({
        outline: [
          [-29, -15], [29, -15],
          [27, 15], [-27, 15]
        ],
        cutouts: [],
        engravings: [
          { type: "rect", x: -23, y: -11, w: 46, h: 22 },
          { type: "circle", x: 0, y: 10, r: 2 }
        ]
      })
    },
    {
      id: "TAIL-01",
      fileName: "TAIL-01.svg",
      name: "Taillight & Fuel Cap Rear Panel",
      category: "Details",
      color: "#212529",
      step: 7,
      width: 66,
      length: 16,
      sheet: 1,
      fileSizeKB: "1.7 KB",
      assembledPos: [116, 20, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [20, 0, 0],
      connections: ["BLK-08"],
      generate2D: () => ({
        outline: [[-33, -8], [33, -8], [33, 8], [-33, 8]],
        cutouts: [
          { x: -24, y: 0, w: 2.5, h: 9 },
          { x: -19, y: 0, w: 2.5, h: 9 },
          { x: -14, y: 0, w: 2.5, h: 9 },
          { x: 14, y: 0, w: 2.5, h: 9 },
          { x: 19, y: 0, w: 2.5, h: 9 },
          { x: 24, y: 0, w: 2.5, h: 9 },
          { x: 0, y: 0, w: 7, h: 7 }
        ],
        engravings: [{ type: "circle", x: 0, y: 0, r: 4 }]
      })
    },
    {
      id: "BMPR-R",
      fileName: "BMPR-R.svg",
      name: "Rear Chrome Blade Bumper",
      category: "Details",
      color: "#ced4da",
      step: 7,
      width: 72,
      length: 7,
      sheet: 1,
      fileSizeKB: "1.1 KB",
      assembledPos: [120, 14, 0],
      assembledRot: [0, 1.5707963267948966, 0],
      explodeVec: [18, 0, 0],
      connections: ["BLK-08"],
      generate2D: () => ({
        outline: [[-36, -3.5], [36, -3.5], [34, 3.5], [-34, 3.5]],
        cutouts: [],
        engravings: [{ type: "line", x1: -32, y1: 0, x2: 32, y2: 0 }]
      })
    },

    // -------------------------------------------------------------
    // 8. AXLES & CIRCULAR LAYERED WHEELS (Step 8)
    // -------------------------------------------------------------
    {
      id: "AXLE-F",
      fileName: "AXLE-F.svg",
      name: "Front Wheel Axle Crossbeam",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 9,
      length: 90,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [-72, 14, 0],
      assembledRot: [1.5707963267948966, 0, 0],
      explodeVec: [0, -12, 0],
      connections: ["CHASSIS-01"],
      generate2D: (t) => ({
        outline: [
          [-4.5, -45],
          [-2.5, -45 - t], [2.5, -45 - t], [4.5, -45],
          [4.5, 45],
          [2.5, 45 + t], [-2.5, 45 + t], [-4.5, 45]
        ],
        cutouts: [
          { x: 0, y: -22, w: 3.5, h: 3.5 },
          { x: 0, y: 22, w: 3.5, h: 3.5 }
        ],
        engravings: []
      })
    },
    {
      id: "AXLE-R",
      fileName: "AXLE-R.svg",
      name: "Rear Wheel Axle Crossbeam",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 9,
      length: 90,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [72, 14, 0],
      assembledRot: [1.5707963267948966, 0, 0],
      explodeVec: [0, -12, 0],
      connections: ["CHASSIS-01"],
      generate2D: (t) => ({
        outline: [
          [-4.5, -45],
          [-2.5, -45 - t], [2.5, -45 - t], [4.5, -45],
          [4.5, 45],
          [2.5, 45 + t], [-2.5, 45 + t], [-4.5, 45]
        ],
        cutouts: [
          { x: 0, y: -22, w: 3.5, h: 3.5 },
          { x: 0, y: 22, w: 3.5, h: 3.5 }
        ],
        engravings: []
      })
    },
    // Front-Left Circular Wheel Stack
    {
      id: "W-FL-L1",
      fileName: "W-FL-L1.svg",
      name: "Front-Left Circular Tire Rim Backing",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [-72, 14, -38],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -18],
      connections: ["AXLE-F"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-FL-ROTOR",
      fileName: "W-FL-ROTOR.svg",
      name: "Front-Left Circular Brake Rotor",
      category: "Mechanical",
      color: "#ced4da",
      step: 8,
      width: 20,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [-72, 14, -40],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -14],
      connections: ["W-FL-L1"],
      generate2D: () => ({
        outline: [
          [10, 0], [9.24, 3.83], [7.07, 7.07], [3.83, 9.24],
          [0, 10], [-3.83, 9.24], [-7.07, 7.07], [-9.24, 3.83],
          [-10, 0], [-9.24, -3.83], [-7.07, -7.07], [-3.83, -9.24],
          [0, -10], [3.83, -9.24], [7.07, -7.07], [9.24, -3.83]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 8.5 }]
      })
    },
    {
      id: "W-FL-L2",
      fileName: "W-FL-L2.svg",
      name: "Front-Left Circular Tire Core",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [-72, 14, -42],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -18],
      connections: ["W-FL-ROTOR"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-FL-FACE",
      fileName: "W-FL-FACE.svg",
      name: "Front-Left Circular 5-Spoke Face",
      category: "Mechanical",
      color: "#eddcd2",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [-72, 14, -44],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -22],
      connections: ["W-FL-L2"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [
          { x: 0, y: 0, w: 4.5, h: 4.5 },
          { x: 0, y: 7.5, w: 3.5, h: 3.5 }, { x: 7.1, y: 2.3, w: 3.5, h: 3.5 },
          { x: 4.4, y: -6.1, w: 3.5, h: 3.5 }, { x: -4.4, y: -6.1, w: 3.5, h: 3.5 },
          { x: -7.1, y: 2.3, w: 3.5, h: 3.5 }
        ],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13 }]
      })
    },
    {
      id: "W-FL-CAP",
      fileName: "W-FL-CAP.svg",
      name: "Front-Left Circular Knockoff Cap",
      category: "Details",
      color: "#ced4da",
      step: 8,
      width: 9,
      length: 9,
      sheet: 1,
      fileSizeKB: "1.1 KB",
      assembledPos: [-72, 14, -46],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -30],
      connections: ["W-FL-FACE"],
      generate2D: () => ({
        outline: [
          [4.5, 0], [4.16, 1.72], [3.18, 3.18], [1.72, 4.16],
          [0, 4.5], [-1.72, 4.16], [-3.18, 3.18], [-4.16, 1.72],
          [-4.5, 0], [-4.16, -1.72], [-3.18, -3.18], [-1.72, -4.16],
          [0, -4.5], [1.72, -4.16], [3.18, -3.18], [4.16, -1.72]
        ],
        cutouts: [],
        engravings: [{ type: "circle", x: 0, y: 0, r: 2 }]
      })
    },
    // Front-Right Circular Wheel Stack
    {
      id: "W-FR-L1",
      fileName: "W-FR-L1.svg",
      name: "Front-Right Circular Tire Rim Backing",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [-72, 14, 38],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 18],
      connections: ["AXLE-F"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-FR-ROTOR",
      fileName: "W-FR-ROTOR.svg",
      name: "Front-Right Circular Brake Rotor",
      category: "Mechanical",
      color: "#ced4da",
      step: 8,
      width: 20,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [-72, 14, 40],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 14],
      connections: ["W-FR-L1"],
      generate2D: () => ({
        outline: [
          [10, 0], [9.24, 3.83], [7.07, 7.07], [3.83, 9.24],
          [0, 10], [-3.83, 9.24], [-7.07, 7.07], [-9.24, 3.83],
          [-10, 0], [-9.24, -3.83], [-7.07, -7.07], [-3.83, -9.24],
          [0, -10], [3.83, -9.24], [7.07, -7.07], [9.24, -3.83]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 8.5 }]
      })
    },
    {
      id: "W-FR-L2",
      fileName: "W-FR-L2.svg",
      name: "Front-Right Circular Tire Core",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [-72, 14, 42],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 18],
      connections: ["W-FR-ROTOR"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-FR-FACE",
      fileName: "W-FR-FACE.svg",
      name: "Front-Right Circular 5-Spoke Face",
      category: "Mechanical",
      color: "#eddcd2",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [-72, 14, 44],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 22],
      connections: ["W-FR-L2"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [
          { x: 0, y: 0, w: 4.5, h: 4.5 },
          { x: 0, y: 7.5, w: 3.5, h: 3.5 }, { x: 7.1, y: 2.3, w: 3.5, h: 3.5 },
          { x: 4.4, y: -6.1, w: 3.5, h: 3.5 }, { x: -4.4, y: -6.1, w: 3.5, h: 3.5 },
          { x: -7.1, y: 2.3, w: 3.5, h: 3.5 }
        ],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13 }]
      })
    },
    {
      id: "W-FR-CAP",
      fileName: "W-FR-CAP.svg",
      name: "Front-Right Circular Knockoff Cap",
      category: "Details",
      color: "#ced4da",
      step: 8,
      width: 9,
      length: 9,
      sheet: 1,
      fileSizeKB: "1.1 KB",
      assembledPos: [-72, 14, 46],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 30],
      connections: ["W-FR-FACE"],
      generate2D: () => ({
        outline: [
          [4.5, 0], [4.16, 1.72], [3.18, 3.18], [1.72, 4.16],
          [0, 4.5], [-1.72, 4.16], [-3.18, 3.18], [-4.16, 1.72],
          [-4.5, 0], [-4.16, -1.72], [-3.18, -3.18], [-1.72, -4.16],
          [0, -4.5], [1.72, -4.16], [3.18, -3.18], [4.16, -1.72]
        ],
        cutouts: [],
        engravings: [{ type: "circle", x: 0, y: 0, r: 2 }]
      })
    },
    // Rear-Left Circular Wheel Stack
    {
      id: "W-RL-L1",
      fileName: "W-RL-L1.svg",
      name: "Rear-Left Circular Tire Rim Backing",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [72, 14, -38],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -18],
      connections: ["AXLE-R"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-RL-ROTOR",
      fileName: "W-RL-ROTOR.svg",
      name: "Rear-Left Circular Brake Rotor",
      category: "Mechanical",
      color: "#ced4da",
      step: 8,
      width: 20,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [72, 14, -40],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -14],
      connections: ["W-RL-L1"],
      generate2D: () => ({
        outline: [
          [10, 0], [9.24, 3.83], [7.07, 7.07], [3.83, 9.24],
          [0, 10], [-3.83, 9.24], [-7.07, 7.07], [-9.24, 3.83],
          [-10, 0], [-9.24, -3.83], [-7.07, -7.07], [-3.83, -9.24],
          [0, -10], [3.83, -9.24], [7.07, -7.07], [9.24, -3.83]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 8.5 }]
      })
    },
    {
      id: "W-RL-L2",
      fileName: "W-RL-L2.svg",
      name: "Rear-Left Circular Tire Core",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [72, 14, -42],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -18],
      connections: ["W-RL-ROTOR"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-RL-FACE",
      fileName: "W-RL-FACE.svg",
      name: "Rear-Left Circular 5-Spoke Face",
      category: "Mechanical",
      color: "#eddcd2",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [72, 14, -44],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -22],
      connections: ["W-RL-L2"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [
          { x: 0, y: 0, w: 4.5, h: 4.5 },
          { x: 0, y: 7.5, w: 3.5, h: 3.5 }, { x: 7.1, y: 2.3, w: 3.5, h: 3.5 },
          { x: 4.4, y: -6.1, w: 3.5, h: 3.5 }, { x: -4.4, y: -6.1, w: 3.5, h: 3.5 },
          { x: -7.1, y: 2.3, w: 3.5, h: 3.5 }
        ],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13 }]
      })
    },
    {
      id: "W-RL-CAP",
      fileName: "W-RL-CAP.svg",
      name: "Rear-Left Circular Knockoff Cap",
      category: "Details",
      color: "#ced4da",
      step: 8,
      width: 9,
      length: 9,
      sheet: 1,
      fileSizeKB: "1.1 KB",
      assembledPos: [72, 14, -46],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, -30],
      connections: ["W-RL-FACE"],
      generate2D: () => ({
        outline: [
          [4.5, 0], [4.16, 1.72], [3.18, 3.18], [1.72, 4.16],
          [0, 4.5], [-1.72, 4.16], [-3.18, 3.18], [-4.16, 1.72],
          [-4.5, 0], [-4.16, -1.72], [-3.18, -3.18], [-1.72, -4.16],
          [0, -4.5], [1.72, -4.16], [3.18, -3.18], [4.16, -1.72]
        ],
        cutouts: [],
        engravings: [{ type: "circle", x: 0, y: 0, r: 2 }]
      })
    },
    // Rear-Right Circular Wheel Stack
    {
      id: "W-RR-L1",
      fileName: "W-RR-L1.svg",
      name: "Rear-Right Circular Tire Rim Backing",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [72, 14, 38],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 18],
      connections: ["AXLE-R"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-RR-ROTOR",
      fileName: "W-RR-ROTOR.svg",
      name: "Rear-Right Circular Brake Rotor",
      category: "Mechanical",
      color: "#ced4da",
      step: 8,
      width: 20,
      length: 20,
      sheet: 1,
      fileSizeKB: "1.3 KB",
      assembledPos: [72, 14, 40],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 14],
      connections: ["W-RR-L1"],
      generate2D: () => ({
        outline: [
          [10, 0], [9.24, 3.83], [7.07, 7.07], [3.83, 9.24],
          [0, 10], [-3.83, 9.24], [-7.07, 7.07], [-9.24, 3.83],
          [-10, 0], [-9.24, -3.83], [-7.07, -7.07], [-3.83, -9.24],
          [0, -10], [3.83, -9.24], [7.07, -7.07], [9.24, -3.83]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 8.5 }]
      })
    },
    {
      id: "W-RR-L2",
      fileName: "W-RR-L2.svg",
      name: "Rear-Right Circular Tire Core",
      category: "Mechanical",
      color: "#212529",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.4 KB",
      assembledPos: [72, 14, 42],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 18],
      connections: ["W-RR-ROTOR"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [{ x: 0, y: 0, w: 4.5, h: 4.5 }],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13.5 }]
      })
    },
    {
      id: "W-RR-FACE",
      fileName: "W-RR-FACE.svg",
      name: "Rear-Right Circular 5-Spoke Face",
      category: "Mechanical",
      color: "#eddcd2",
      step: 8,
      width: 30,
      length: 30,
      sheet: 1,
      fileSizeKB: "1.8 KB",
      assembledPos: [72, 14, 44],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 22],
      connections: ["W-RR-L2"],
      generate2D: () => ({
        outline: [
          [15, 0], [13.86, 5.74], [10.61, 10.61], [5.74, 13.86],
          [0, 15], [-5.74, 13.86], [-10.61, 10.61], [-13.86, 5.74],
          [-15, 0], [-13.86, -5.74], [-10.61, -10.61], [-5.74, -13.86],
          [0, -15], [5.74, -13.86], [10.61, -10.61], [13.86, -5.74]
        ],
        cutouts: [
          { x: 0, y: 0, w: 4.5, h: 4.5 },
          { x: 0, y: 7.5, w: 3.5, h: 3.5 }, { x: 7.1, y: 2.3, w: 3.5, h: 3.5 },
          { x: 4.4, y: -6.1, w: 3.5, h: 3.5 }, { x: -4.4, y: -6.1, w: 3.5, h: 3.5 },
          { x: -7.1, y: 2.3, w: 3.5, h: 3.5 }
        ],
        engravings: [{ type: "circle", x: 0, y: 0, r: 13 }]
      })
    },
    {
      id: "W-RR-CAP",
      fileName: "W-RR-CAP.svg",
      name: "Rear-Right Circular Knockoff Cap",
      category: "Details",
      color: "#ced4da",
      step: 8,
      width: 9,
      length: 9,
      sheet: 1,
      fileSizeKB: "1.1 KB",
      assembledPos: [72, 14, 46],
      assembledRot: [0, 0, 0],
      explodeVec: [0, 0, 30],
      connections: ["W-RR-FACE"],
      generate2D: () => ({
        outline: [
          [4.5, 0], [4.16, 1.72], [3.18, 3.18], [1.72, 4.16],
          [0, 4.5], [-1.72, 4.16], [-3.18, 3.18], [-4.16, 1.72],
          [-4.5, 0], [-4.16, -1.72], [-3.18, -3.18], [-1.72, -4.16],
          [0, -4.5], [1.72, -4.16], [3.18, -3.18], [4.16, -1.72]
        ],
        cutouts: [],
        engravings: [{ type: "circle", x: 0, y: 0, r: 2 }]
      })
    }
  ]
};