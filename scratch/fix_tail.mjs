import fs from 'fs';

let txt = fs.readFileSync('js/models/my-model.js', 'utf8');

// Find TAIL-01
const p1 = txt.indexOf('"TAIL-01"');
const p2 = txt.indexOf('id: "TAIL-01"');
const idx = p2 >= 0 ? p2 : p1;
console.log('TAIL-01 index:', idx);
console.log('Snippet:\n', txt.substring(idx, idx + 800));

// Replace generate2D of TAIL-01
const oldGen = txt.substring(idx).match(/generate2D:\s*\(\)\s*=>\s*\(\{[\s\S]*?\}\)/);
console.log('Old generator match:', oldGen ? oldGen[0] : 'not found');

if (oldGen) {
  const replacement = `generate2D: (t, kerf, clr) => {
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
  txt = txt.replace(oldGen[0], replacement);
  fs.writeFileSync('js/models/my-model.js', txt, 'utf8');
  console.log('Successfully replaced TAIL-01 generate2D in my-model.js!');
}
