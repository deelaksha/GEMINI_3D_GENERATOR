import fs from 'fs';

let content = fs.readFileSync('./js/models/cathedral.js', 'utf8');

// Replace assembledPos for CH-26 to CH-29 and add type: 'decorative'
content = content.replace(/assembledPos: \[-65, 9, -18\],/g, 'assembledPos: (t = 3.0) => [-65, 9 + t / 2, -18],');
content = content.replace(/assembledPos: \[-65, 9, 18\],/g, 'assembledPos: (t = 3.0) => [-65, 9 + t / 2, 18],');
content = content.replace(/assembledPos: \[-35, 9, -18\],/g, 'assembledPos: (t = 3.0) => [-35, 9 + t / 2, -18],');
content = content.replace(/assembledPos: \[-35, 9, 18\],/g, 'assembledPos: (t = 3.0) => [-35, 9 + t / 2, 18],');
content = content.replace(/cutouts: \[{ x: 0, y: 2, w: 20, h: 4 }\]/g, "cutouts: [{ x: 0, y: 2, w: 20, h: 4, type: 'decorative' }]");

// CH-30, 31, 32
content = content.replace(/assembledPos: \[-10, 16, -22\],/g, 'assembledPos: (t = 3.0) => [-10, 16 + t / 2, -22],');
content = content.replace(/assembledPos: \[85, 14, 0\],/g, 'assembledPos: (t = 3.0) => [85, 14 + t / 2, 0],');
content = content.replace(/assembledPos: \[-95, 11, 0\],/g, 'assembledPos: (t = 3.0) => [-95, 11 + t / 2, 0],');

// CH-02, 03, 04, 05
content = content.replace(/assembledPos: \[-57, 32.5, -36\],/g, 'assembledPos: (t = 3.0) => [-57, 32.5 + t / 2, -36],');
content = content.replace(/assembledPos: \[85, 32.5, -36\],/g, 'assembledPos: (t = 3.0) => [85, 32.5 + t / 2, -36],');
content = content.replace(/assembledPos: \[-57, 32.5, 36\],/g, 'assembledPos: (t = 3.0) => [-57, 32.5 + t / 2, 36],');
content = content.replace(/assembledPos: \[85, 32.5, 36\],/g, 'assembledPos: (t = 3.0) => [85, 32.5 + t / 2, 36],');

// CH-09, 10
content = content.replace(/assembledPos: \[115, 52.5, 0\],/g, 'assembledPos: (t = 3.0) => [115, 52.5 + t / 2, 0],');
content = content.replace(/assembledPos: \[5, 45, 0\],/g, 'assembledPos: (t = 3.0) => [5, 45 + t / 2, 0],');

// CH-06, 07
content = content.replace(/assembledPos: \[30, 47.5, -85\],/g, 'assembledPos: (t = 3.0) => [30, 47.5 + t / 2, -85],');
content = content.replace(/assembledPos: \[30, 47.5, 85\],/g, 'assembledPos: (t = 3.0) => [30, 47.5 + t / 2, 85],');

// CH-15, 16, 17, 18
content = content.replace(/assembledPos: \[-80, 22, -45\],/g, 'assembledPos: (t = 3.0) => [-80, 22 + t / 2, -45],');
content = content.replace(/assembledPos: \[-35, 22, -45\],/g, 'assembledPos: (t = 3.0) => [-35, 22 + t / 2, -45],');
content = content.replace(/assembledPos: \[-80, 22, 45\],/g, 'assembledPos: (t = 3.0) => [-80, 22 + t / 2, 45],');
content = content.replace(/assembledPos: \[-35, 22, 45\],/g, 'assembledPos: (t = 3.0) => [-35, 22 + t / 2, 45],');

// CH-08
content = content.replace(/assembledPos: \[-115, 60, 0\],/g, 'assembledPos: (t = 3.0) => [-115, 60 + t / 2, 0],');

// Bell towers CH-19..22 (parapet Y = 120, height 90, center Y = 120 + 45 = 165)
content = content.replace(/assembledPos: \[-115, 115, -26\],/g, 'assembledPos: (t = 3.0) => [-115, 165 + t / 2, -26],');
content = content.replace(/assembledPos: \[-103, 115, -36\],/g, 'assembledPos: (t = 3.0) => [-103, 165 + t / 2, -36],');
content = content.replace(/assembledPos: \[-115, 115, 26\],/g, 'assembledPos: (t = 3.0) => [-115, 165 + t / 2, 26],');
content = content.replace(/assembledPos: \[-103, 115, 36\],/g, 'assembledPos: (t = 3.0) => [-103, 165 + t / 2, 36],');

// CH-11 and CH-12 cutout #2 edge margin fix
content = content.replace(/\{ x: 100, y: 22, w: t \+ 0\.1, h: 10 \}/g, '{ x: 100, y: 20, w: t + 0.1, h: 8 }');

// CH-13 and CH-14 transept roof length fix (44mm length)
content = content.replace(/outline: \[\[-24, -25\], \[24, -25\], \[24, 25\], \[-24, 25\]\],/g, 'outline: [[-24, -22], [24, -22], [24, 22], [-24, 22]],');

// CH-24 Spire cutout
content = content.replace(/cutouts: \[{ x: 0, y: 0, w: t \+ 0\.1, h: 30 }\]/g, 'cutouts: [{ x: 0, y: -8, w: t + 0.1, h: 16 }]');

fs.writeFileSync('./js/models/cathedral.js', content, 'utf8');
console.log('Cathedral file updated successfully!');
