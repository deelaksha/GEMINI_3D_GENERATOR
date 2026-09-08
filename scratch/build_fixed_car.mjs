import fs from 'fs';

let src = fs.readFileSync('scratch/car_code_dump.js', 'utf8');

// 1. Export header
src = src.replace(/^const ClassicCarModelData =/, 'export const ClassicCarModelData =');

// 2. 4 Manufacturing Sheets
const sheetsBlock = `  manufacturingSheets: [
    {
      sheetNum: 1,
      name: "car_sheet_01_chassis.svg",
      desc: "Chassis floor pan, spine backbone, rails, and rocker sills.",
      sheetW: 600,
      sheetH: 400,
      partIds: ["CHASSIS-01", "SPINE-01", "FRAME-L", "FRAME-R", "SILL-L", "SILL-R", "WAIST-L", "WAIST-R", "ARCH-BRACE-FL", "ARCH-BRACE-FR", "ARCH-BRACE-RL", "ARCH-BRACE-RR"],
      layout: {
        "CHASSIS-01": { x: 140, y: 70, r: 0 },
        "SPINE-01": { x: 410, y: 35, r: 0 },
        "FRAME-L": { x: 140, y: 155, r: 0 },
        "FRAME-R": { x: 410, y: 155, r: 0 },
        "SILL-L": { x: 140, y: 225, r: 0 },
        "SILL-R": { x: 410, y: 225, r: 0 },
        "WAIST-L": { x: 140, y: 295, r: 0 },
        "WAIST-R": { x: 410, y: 295, r: 0 },
        "ARCH-BRACE-FL": { x: 80, y: 360, r: 0 },
        "ARCH-BRACE-FR": { x: 220, y: 360, r: 0 },
        "ARCH-BRACE-RL": { x: 360, y: 360, r: 0 },
        "ARCH-BRACE-RR": { x: 500, y: 360, r: 0 }
      }
    },
    {
      sheetNum: 2,
      name: "car_sheet_02_bulkheads.svg",
      desc: "Transverse bulkheads, dashboard, console, and bucket seats.",
      sheetW: 600,
      sheetH: 400,
      partIds: ["BLK-01", "BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07", "BLK-08", "DASH-01", "STEER-01", "CONSOLE-01", "SEAT-L-BASE", "SEAT-L-BACK", "SEAT-R-BASE", "SEAT-R-BACK"],
      layout: {
        "BLK-01": { x: 60, y: 60, r: 0 },
        "BLK-02": { x: 180, y: 60, r: 0 },
        "BLK-03": { x: 300, y: 60, r: 0 },
        "BLK-04": { x: 420, y: 60, r: 0 },
        "BLK-05": { x: 530, y: 60, r: 0 },
        "BLK-06": { x: 60, y: 160, r: 0 },
        "BLK-07": { x: 180, y: 160, r: 0 },
        "BLK-08": { x: 300, y: 160, r: 0 },
        "DASH-01": { x: 440, y: 160, r: 0 },
        "STEER-01": { x: 540, y: 160, r: 0 },
        "CONSOLE-01": { x: 100, y: 270, r: 0 },
        "SEAT-L-BASE": { x: 250, y: 270, r: 0 },
        "SEAT-L-BACK": { x: 390, y: 270, r: 0 },
        "SEAT-R-BASE": { x: 250, y: 350, r: 0 },
        "SEAT-R-BACK": { x: 390, y: 350, r: 0 }
      }
    },
    {
      sheetNum: 3,
      name: "car_sheet_03_bodywork.svg",
      desc: "Fenders, hood, windshield, roof louvers, doors, and rear decklid.",
      sheetW: 600,
      sheetH: 400,
      partIds: ["GRILL-01", "BMPR-F", "HOOD-01", "FEND-FL", "FEND-FR", "WINDSHIELD-01", "ROOF-01", "REAR-WINDOW-01", "LOUVER-01", "LOUVER-02", "LOUVER-03", "QTR-RL", "QTR-RR", "DOOR-L", "DOOR-R", "TRUNK-01", "TAIL-01", "BMPR-R"],
      layout: {
        "GRILL-01": { x: 70, y: 50, r: 0 },
        "BMPR-F": { x: 200, y: 50, r: 0 },
        "HOOD-01": { x: 350, y: 60, r: 0 },
        "FEND-FL": { x: 500, y: 60, r: 0 },
        "FEND-FR": { x: 100, y: 140, r: 0 },
        "WINDSHIELD-01": { x: 250, y: 140, r: 0 },
        "ROOF-01": { x: 410, y: 150, r: 0 },
        "REAR-WINDOW-01": { x: 530, y: 150, r: 0 },
        "LOUVER-01": { x: 70, y: 230, r: 0 },
        "LOUVER-02": { x: 190, y: 230, r: 0 },
        "LOUVER-03": { x: 310, y: 230, r: 0 },
        "QTR-RL": { x: 440, y: 240, r: 0 },
        "QTR-RR": { x: 540, y: 240, r: 0 },
        "DOOR-L": { x: 100, y: 320, r: 0 },
        "DOOR-R": { x: 250, y: 320, r: 0 },
        "TRUNK-01": { x: 390, y: 320, r: 0 },
        "TAIL-01": { x: 500, y: 320, r: 0 },
        "BMPR-R": { x: 300, y: 380, r: 0 }
      }
    },
    {
      sheetNum: 4,
      name: "car_sheet_04_wheels.svg",
      desc: "Cross-axles and 4 true-circular layered wheel assemblies.",
      sheetW: 600,
      sheetH: 400,
      partIds: ["AXLE-F", "AXLE-R", "W-FL-L1", "W-FL-ROTOR", "W-FL-L2", "W-FL-FACE", "W-FL-CAP", "W-FR-L1", "W-FR-ROTOR", "W-FR-L2", "W-FR-FACE", "W-FR-CAP", "W-RL-L1", "W-RL-ROTOR", "W-RL-L2", "W-RL-FACE", "W-RL-CAP", "W-RR-L1", "W-RR-ROTOR", "W-RR-L2", "W-RR-FACE", "W-RR-CAP"],
      layout: {
        "AXLE-F": { x: 150, y: 40, r: 0 },
        "AXLE-R": { x: 450, y: 40, r: 0 },
        "W-FL-L1": { x: 70, y: 110, r: 0 },
        "W-FL-ROTOR": { x: 160, y: 110, r: 0 },
        "W-FL-L2": { x: 250, y: 110, r: 0 },
        "W-FL-FACE": { x: 340, y: 110, r: 0 },
        "W-FL-CAP": { x: 410, y: 110, r: 0 },
        "W-FR-L1": { x: 70, y: 180, r: 0 },
        "W-FR-ROTOR": { x: 160, y: 180, r: 0 },
        "W-FR-L2": { x: 250, y: 180, r: 0 },
        "W-FR-FACE": { x: 340, y: 180, r: 0 },
        "W-FR-CAP": { x: 410, y: 180, r: 0 },
        "W-RL-L1": { x: 70, y: 250, r: 0 },
        "W-RL-ROTOR": { x: 160, y: 250, r: 0 },
        "W-RL-L2": { x: 250, y: 250, r: 0 },
        "W-RL-FACE": { x: 340, y: 250, r: 0 },
        "W-RL-CAP": { x: 410, y: 250, r: 0 },
        "W-RR-L1": { x: 70, y: 320, r: 0 },
        "W-RR-ROTOR": { x: 160, y: 320, r: 0 },
        "W-RR-L2": { x: 250, y: 320, r: 0 },
        "W-RR-FACE": { x: 340, y: 320, r: 0 },
        "W-RR-CAP": { x: 410, y: 320, r: 0 }
      }
    }
  ],`;

src = src.replace(/manufacturingSheets:\s*\[[\s\S]*?\n\s*\],/, sheetsBlock);

// 3. Assign sheet numbers in parts
const s2Parts = ["BLK-01", "BLK-02", "BLK-03", "BLK-04", "BLK-05", "BLK-06", "BLK-07", "BLK-08", "DASH-01", "STEER-01", "CONSOLE-01", "SEAT-L-BASE", "SEAT-L-BACK", "SEAT-R-BASE", "SEAT-R-BACK"];
const s3Parts = ["GRILL-01", "BMPR-F", "HOOD-01", "FEND-FL", "FEND-FR", "WINDSHIELD-01", "ROOF-01", "REAR-WINDOW-01", "LOUVER-01", "LOUVER-02", "LOUVER-03", "QTR-RL", "QTR-RR", "DOOR-L", "DOOR-R", "TRUNK-01", "TAIL-01", "BMPR-R"];
const s4Parts = ["AXLE-F", "AXLE-R", "W-FL-L1", "W-FL-ROTOR", "W-FL-L2", "W-FL-FACE", "W-FL-CAP", "W-FR-L1", "W-FR-ROTOR", "W-FR-L2", "W-FR-FACE", "W-FR-CAP", "W-RL-L1", "W-RL-ROTOR", "W-RL-L2", "W-RL-FACE", "W-RL-CAP", "W-RR-L1", "W-RR-ROTOR", "W-RR-L2", "W-RR-FACE", "W-RR-CAP"];

for (const id of s2Parts) {
  const reg = new RegExp(`(id:\\s*["']${id}["'][\\s\\S]*?sheet:\\s*)1`, 'g');
  src = src.replace(reg, '$12');
}
for (const id of s3Parts) {
  const reg = new RegExp(`(id:\\s*["']${id}["'][\\s\\S]*?sheet:\\s*)1`, 'g');
  src = src.replace(reg, '$13');
}
for (const id of s4Parts) {
  const reg = new RegExp(`(id:\\s*["']${id}["'][\\s\\S]*?sheet:\\s*)1`, 'g');
  src = src.replace(reg, '$14');
}

// 4. Update CHASSIS-01 generate2D with synchronized slots
const oldChassisGen = /id:\s*"CHASSIS-01"[\s\S]*?generate2D:\s*\(t, kerf, clr\) => \{[\s\S]*?return \{[\s\S]*?cutouts:\s*cutouts,[\s\S]*?engravings:[\s\S]*?\}\s*;\s*\}/;

const newChassisGen = `id: "CHASSIS-01",
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
        const spineSlots = [-85, 0, 85];
        const railSlots = [-70, 70];
        const cutouts = [
          // Synchronized slots matching SPINE-01 three 20mm tenon tabs
          ...spineSlots.map(x => ({ x: x, y: 0, w: 20 + clr, h: sw })),
          // Synchronized slots matching FRAME-L and FRAME-R 20mm tabs
          ...railSlots.map(x => ({ x: x, y: -22, w: 20 + clr, h: sw })),
          ...railSlots.map(x => ({ x: x, y: 22, w: 20 + clr, h: sw }))
        ];
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
      }`;

src = src.replace(oldChassisGen, newChassisGen);

// 5. Update SPINE-01 generate2D with downward half-lap slots
const oldSpineGen = /id:\s*"SPINE-01"[\s\S]*?generate2D:\s*\(t, kerf, clr\) => \{[\s\S]*?return \{[\s\S]*?outline:[\s\S]*?cutouts:[\s\S]*?engravings:[\s\S]*?\}\s*;\s*\}/;

const newSpineGen = `id: "SPINE-01",
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
            [-10, -9], [-10, -9 - t], [10, -9 - t], [10, -9],
            [75, -9], [75, -9 - t], [95, -9 - t], [95, -9],
            [115, -9], [115, 9], [-115, 9]
          ],
          // Half-lap slots cutting downward from top edge y=9 to y=0.8 (depth 8.2mm)
          cutouts: bXs.map(x => ({ x: x, y: 4.9, w: sw, h: 8.2 })),
          engravings: []
        };
      }`;

src = src.replace(oldSpineGen, newSpineGen);

// 6. Update bulkheads BLK-01 to BLK-08: upward half-lap slots from bottom edge
const blkConfigs = [
  { id: 'BLK-01', bottomY: -13, slotCenterY: -8.9 },
  { id: 'BLK-02', bottomY: -15, slotCenterY: -10.9 },
  { id: 'BLK-03', bottomY: -19, slotCenterY: -14.9 },
  { id: 'BLK-04', bottomY: -20, slotCenterY: -15.9 },
  { id: 'BLK-05', bottomY: -20, slotCenterY: -15.9 },
  { id: 'BLK-06', bottomY: -19, slotCenterY: -14.9 },
  { id: 'BLK-07', bottomY: -16, slotCenterY: -11.9 },
  { id: 'BLK-08', bottomY: -13, slotCenterY: -8.9 }
];

for (const cfg of blkConfigs) {
  // Replace center cutout with upward half-lap slot of depth 8.2mm
  const regCenterCutout = new RegExp(`(id:\\s*["']${cfg.id}["'][\\s\\S]*?cutouts:\\s*\\[\\s*)\\{\\s*x:\\s*0,\\s*y:\\s*-[0-9.]+,\\s*w:\\s*sw,\\s*h:\\s*[0-9.]+\\s*\\}`);
  src = src.replace(regCenterCutout, `$1{ x: 0, y: ${cfg.slotCenterY}, w: sw, h: 8.2 }`);

  // Flatten bottom outline tab so bulkhead rests flush on chassis pan
  const regBottomTab = new RegExp(`(id:\\s*["']${cfg.id}["'][\\s\\S]*?outline:\\s*\\[\\s*\\[-[0-9.]+,\\s*${cfg.bottomY}\\],\\s*)\\[-[0-9.]+,\\s*${cfg.bottomY}\\],\\s*\\[-[0-9.]+,\\s*${cfg.bottomY}\\s*-\\s*t\\],\\s*\\[[0-9.]+,\\s*${cfg.bottomY}\\s*-\\s*t\\],\\s*\\[[0-9.]+,\\s*${cfg.bottomY}\\],`);
  src = src.replace(regBottomTab, `$1`);
}

// 7. Fix TAIL-01 mortise slots
const oldTailGen = `generate2D: () => ({
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
      })`;

const newTailGen = `generate2D: (t, kerf, clr) => {
        const sw = (t || 3.0) + (clr || 0.10);
        return {
          outline: [[-33, -8], [33, -8], [33, 8], [-33, 8]],
          cutouts: [
            { x: -24, y: 0, w: sw, h: 9 },
            { x: -19, y: 0, w: sw, h: 9 },
            { x: -14, y: 0, w: sw, h: 9 },
            { x: 14, y: 0, w: sw, h: 9 },
            { x: 19, y: 0, w: sw, h: 9 },
            { x: 24, y: 0, w: sw, h: 9 },
            { x: 0, y: 0, w: 7, h: 7 }
          ],
          engravings: [{ type: "circle", x: 0, y: 0, r: 4 }]
        };
      }`;

src = src.replace(oldTailGen, newTailGen);

// 8. Append exports
src += `

export const MyModelData = ClassicCarModelData;
export default ClassicCarModelData;
`;

fs.writeFileSync('js/models/my-model.js', src, 'utf8');
console.log('Successfully wrote updated js/models/my-model.js! Length:', src.length);
