import fs from 'fs';
import { DesignParser } from '../js/services/design-parser.js';

async function test() {
  const code = fs.readFileSync('js/models/cathedral.js', 'utf8');
  console.time('parse Cathedral');
  const res = await DesignParser.parseAndValidate(code);
  console.timeEnd('parse Cathedral');
  console.log('Success:', res.success, 'parts:', res.modelData?.parts?.length, 'error:', res.error);
}
test();
