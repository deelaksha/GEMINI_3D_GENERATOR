import fs from 'fs';

let src = fs.readFileSync('scratch/car_code_dump.js', 'utf8');

// 1. Update header declaration
src = src.replace(/^const ClassicCarModelData =/, 'export const ClassicCarModelData =');

// 2. Define 4 sheets replacement
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

// 4. Fix TAIL-01 mortise slots
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

// 5. Append exports
src += `

export const MyModelData = ClassicCarModelData;
export default ClassicCarModelData;
`;

fs.writeFileSync('js/models/my-model.js', src, 'utf8');
console.log('Successfully wrote js/models/my-model.js directly from source template! Length:', src.length);
