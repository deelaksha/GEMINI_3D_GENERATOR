/**
 * Design Parser & Evaluator
 * Parses and validates 3D model definitions. A JSON model definition is always accepted. JavaScript is run (as an ES
 * module, in this page - it is NOT sandboxed) only for code the user typed into the local code editor; designs
 * fetched from Firestore, the local cache or a URL must be JSON data: data-only is the default, and only the editor
 * passes { allowCode: true }.
 * Never crashes the active 3D scene or page.
 */

export class DesignParser {
  /**
   * Safely evaluates JavaScript code and extracts the model definition object.
   * @param {string} rawCode - User supplied JavaScript / ES Module code, or a JSON model definition
   * @param {{allowCode?: boolean}} [options] - allowCode (default false): run JavaScript; only for code typed in the editor
   * @returns {Promise<{success: boolean, modelData?: Object, error?: Object, warnings?: Array<string>}>}
   */
  static async parseAndValidate(rawCode, { allowCode = false } = {}) {
    if (!rawCode || !rawCode.trim()) {
      return {
        success: false,
        error: {
          message: 'Code cannot be empty.',
          line: 1,
          suggestion: 'Paste a valid ConstructionObject JavaScript definition or load a template.'
        }
      };
    }

    // Step 1: JSON model data, or (allowCode only) the editor code run as a Blob module
    let evaluatedResult = null;
    let evalError = null;

    try {
      evaluatedResult = await this.evaluateCode(rawCode, allowCode);
    } catch (err) {
      evalError = this.normalizeError(err, rawCode);
      return {
        success: false,
        error: evalError
      };
    }

    // Step 2: Extract model data object
    const modelData = this.extractModelObject(evaluatedResult);
    if (!modelData) {
      return {
        success: false,
        error: {
          message: 'No valid model definition exported or returned.',
          line: 1,
          suggestion: 'Ensure your code exports your model using "export default { ... }" or "export const MyModelData = { ... }".'
        }
      };
    }

    // Step 3: Deep structural and geometric validation
    const validation = this.validateSchema(modelData);
    if (!validation.isValid) {
      return {
        success: false,
        error: {
          message: validation.error,
          line: validation.line || 1,
          field: validation.field,
          suggestion: validation.suggestion || 'Review the Model Specification Guide.'
        },
        warnings: validation.warnings
      };
    }

    return {
      success: true,
      modelData,
      warnings: validation.warnings
    };
  }

  /**
   * Evaluates ES module code using dynamic Blob URLs with automatic export injection.
   * Seamlessly handles both exported modules and unexported declarations (e.g. const MyModel = { ... }).
   * Without allowCode only a JSON model definition is accepted: stored designs are data, never code.
   */
  static async evaluateCode(rawCode, allowCode = false) {
    if (!rawCode || !rawCode.trim()) return null;
    const trimmed = rawCode.trim();

    // 1. If the user pasted plain JSON, parse directly
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed.id && Array.isArray(parsed.parts)) return parsed;
      } catch (e) {
        // Not valid JSON, continue with JS execution
      }
    }
    if (!allowCode) {
      throw new Error('This design is stored as JavaScript, which is no longer run when a design is loaded. Open it in the code editor to review and run it, or save it as a JSON model definition.');
    }

    // 2. Prepare code for ES Module evaluation
    let moduleCode = rawCode;

    // Detect which variables are already exported to avoid duplicate export syntax errors
    const exportedVars = new Set();
    const exportDeclRegex = /export\s+(?:const|let|var|function|class)\s+([a-zA-Z0-9_$]+)/g;
    for (const m of rawCode.matchAll(exportDeclRegex)) {
      exportedVars.add(m[1]);
    }
    const exportNamedRegex = /export\s*\{([^}]+)\}/g;
    for (const m of rawCode.matchAll(exportNamedRegex)) {
      m[1].split(',').forEach(v => {
        const name = v.trim().split(/\s+as\s+/)[0].trim();
        if (name) exportedVars.add(name);
      });
    }

    const hasExportDefault = /export\s+default\b/.test(rawCode);

    // Find all top-level declared variables that are NOT yet exported
    const unexportedVars = [];
    const allDeclRegex = /(?:^|[\r\n;])\s*(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=/g;
    for (const m of rawCode.matchAll(allDeclRegex)) {
      const varName = m[1];
      if (!exportedVars.has(varName) && !unexportedVars.includes(varName)) {
        unexportedVars.push(varName);
      }
    }

    // Also look for bare top-level assignments like "ClassicCarModelData = { ... }"
    const bareAssignRegex = /(?:^|[\r\n;])\s*([a-zA-Z0-9_$]+)\s*=\s*\{/g;
    for (const m of rawCode.matchAll(bareAssignRegex)) {
      const varName = m[1];
      if (!exportedVars.has(varName) && !unexportedVars.includes(varName) && varName !== 'const' && varName !== 'let' && varName !== 'var') {
        unexportedVars.push(varName);
      }
    }

    // If there are unexported variables, export them so import(blobUrl) can inspect them
    const appendedExports = [];
    if (unexportedVars.length > 0) {
      appendedExports.push(`export { ${unexportedVars.join(', ')} };`);
    }

    if (!hasExportDefault) {
      // Pick the most likely model variable name
      let defaultVar = unexportedVars.find(v => /model|data|car|house|stadium|pavilion|box|vehicle/i.test(v)) || unexportedVars[unexportedVars.length - 1];
      if (defaultVar) {
        appendedExports.push(`export default (typeof ${defaultVar} !== 'undefined' ? ${defaultVar} : undefined);`);
      }
    }

    if (appendedExports.length > 0) {
      moduleCode = `${rawCode}\n\n/* Auto-injected exports for unexported model definitions */\n${appendedExports.join('\n')}\n`;
    } else if (!hasExportDefault && (trimmed.startsWith('{') || trimmed.startsWith('('))) {
      // Bare object literal
      moduleCode = `export default (${trimmed.replace(/;$/, '')});`;
    }

    // The user's own editor code runs as a module from a Blob URL (the only way code is run here)
    const blobUrl = URL.createObjectURL(new Blob([moduleCode], { type: 'application/javascript' }));
    try {
      return await import(blobUrl);
    } finally {
      URL.revokeObjectURL(blobUrl);
    }
  }

  /**
   * Extracts model object from imported module or evaluation result
   */
  static extractModelObject(result) {
    if (!result) return null;

    // If it's already a plain model object with id and parts
    if (result.id && Array.isArray(result.parts)) {
      return result;
    }

    // If result is a function that returns a model
    if (typeof result === 'function') {
      try {
        const fnRes = result();
        if (fnRes && fnRes.id && Array.isArray(fnRes.parts)) return fnRes;
      } catch (e) {}
    }

    // If result is a module namespace or object
    if (typeof result === 'object') {
      // 1. Check default export
      if (result.default) {
        if (typeof result.default === 'object' && result.default.id && Array.isArray(result.default.parts)) {
          return result.default;
        }
        if (typeof result.default === 'function') {
          try {
            const defRes = result.default();
            if (defRes && defRes.id && Array.isArray(defRes.parts)) return defRes;
          } catch (e) {}
        }
      }

      // 2. Check common named exports
      const knownKeys = ['ClassicCarModelData', 'MyModelData', 'modelData', 'ModelData', 'model', 'CathedralModelData', 'SimpleHouseModelData', 'MinimalBoxModel'];
      for (const key of knownKeys) {
        if (result[key] && typeof result[key] === 'object' && result[key].id && Array.isArray(result[key].parts)) {
          return result[key];
        }
      }

      // 3. Scan all exported properties
      for (const val of Object.values(result)) {
        if (val && typeof val === 'object' && val.id && Array.isArray(val.parts)) {
          return val;
        }
        if (typeof val === 'function') {
          try {
            const callRes = val();
            if (callRes && callRes.id && Array.isArray(callRes.parts)) return callRes;
          } catch (e) {}
        }
      }

      // 4. Nested scan (e.g. wrapper objects)
      for (const val of Object.values(result)) {
        if (val && typeof val === 'object') {
          for (const sub of Object.values(val)) {
            if (sub && typeof sub === 'object' && sub.id && Array.isArray(sub.parts)) {
              return sub;
            }
          }
        }
      }
    }

    return null;
  }

  /**
   * Deep structural validation of the model schema
   */
  static validateSchema(model) {
    const warnings = [];

    // Check id
    if (!model.id || typeof model.id !== 'string') {
      return {
        isValid: false,
        field: 'id',
        error: 'Model missing mandatory "id" property (must be a non-empty string).',
        suggestion: 'Add id: "my-design-id" at the root of your model object.'
      };
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(model.id)) {
      warnings.push(`Model id "${model.id}" contains special characters. Hyphens and underscores are recommended.`);
    }

    // Check name
    if (!model.name || typeof model.name !== 'string') {
      return {
        isValid: false,
        field: 'name',
        error: 'Model missing mandatory "name" string property.',
        suggestion: 'Add a human-friendly name, e.g. name: "Modern Villa 1".'
      };
    }

    // Check parts array
    if (!Array.isArray(model.parts) || model.parts.length === 0) {
      return {
        isValid: false,
        field: 'parts',
        error: 'Model must have a "parts" array containing at least 1 part definition.',
        suggestion: 'Define parts: [ { id: "p1", ... } ] with physical part geometries.'
      };
    }

    const seenPartIds = new Set();
    const allPartIds = new Set(model.parts.map(p => p.id));

    for (let i = 0; i < model.parts.length; i++) {
      const part = model.parts[i];
      const partPrefix = `Part #${i + 1} (${part.id || 'unnamed'})`;

      if (!part.id || typeof part.id !== 'string') {
        return {
          isValid: false,
          field: `parts[${i}].id`,
          error: `${partPrefix} is missing a string "id".`,
          suggestion: 'Every part must have a unique identifier string, e.g. id: "base_plate".'
        };
      }

      if (seenPartIds.has(part.id)) {
        return {
          isValid: false,
          field: `parts[${i}].id`,
          error: `Duplicate part id detected: "${part.id}". Part IDs must be strictly unique.`,
          suggestion: `Rename part "${part.id}" to something unique like "${part.id}_2".`
        };
      }
      seenPartIds.add(part.id);

      // Check geometry: supports either generate2D function OR static geometry.outline
      let geo = null;
      if (typeof part.generate2D === 'function') {
        try {
          geo = part.generate2D(3.0, 0.15, 0.10);
          if (!geo || !Array.isArray(geo.outline)) {
            return {
              isValid: false,
              field: `parts[${i}].generate2D`,
              error: `${partPrefix} generate2D() must return an object with an "outline" array.`,
              suggestion: 'Return { outline: [[x1, y1], [x2, y2], ...], cutouts: [] } from generate2D().'
            };
          }
          part.geometry = {
            outline: geo.outline,
            cutouts: geo.cutouts || []
          };
        } catch (fnErr) {
          return {
            isValid: false,
            field: `parts[${i}].generate2D`,
            error: `${partPrefix} generate2D() threw an error during evaluation: ${fnErr.message}`,
            suggestion: 'Ensure generate2D(thickness, kerf, clearance) does not reference undefined variables.'
          };
        }
      } else if (part.geometry && Array.isArray(part.geometry.outline)) {
        geo = part.geometry;
        const staticGeo = part.geometry;
        part.generate2D = function(thickness = 3.0, kerf = 0.15, clearance = 0.10) {
          return {
            outline: staticGeo.outline || [],
            cutouts: staticGeo.cutouts || []
          };
        };
      } else {
        return {
          isValid: false,
          field: `parts[${i}].geometry.outline`,
          error: `${partPrefix} is missing 2D geometry definition (neither "generate2D" function nor "geometry.outline" polygon array was found).`,
          suggestion: 'Provide either generate2D: (t, kerf, clr) => ({ outline: [...] }) or geometry: { outline: [...] }.'
        };
      }

      if (geo.outline.length < 3) {
        return {
          isValid: false,
          field: `parts[${i}].geometry.outline`,
          error: `${partPrefix} outline must have at least 3 points to form a 2D surface.`,
          suggestion: 'Specify at least 3 vertices [ [x1, y1], [x2, y2], [x3, y3] ].'
        };
      }

      // Check each vertex coordinate
      for (let v = 0; v < geo.outline.length; v++) {
        const pt = geo.outline[v];
        if (!Array.isArray(pt) || pt.length < 2 || isNaN(pt[0]) || isNaN(pt[1])) {
          return {
            isValid: false,
            field: `parts[${i}].geometry.outline[${v}]`,
            error: `${partPrefix} outline vertex #${v + 1} is invalid. Expected [x, y] numbers.`,
            suggestion: 'Ensure every coordinate pair is formatted as [number, number].'
          };
        }
      }

      // Check cutouts if provided
      if (geo.cutouts && Array.isArray(geo.cutouts)) {
        for (let c = 0; c < geo.cutouts.length; c++) {
          const cut = geo.cutouts[c];
          if (isNaN(cut.x) || isNaN(cut.y) || isNaN(cut.w) || isNaN(cut.h) || cut.w <= 0 || cut.h <= 0) {
            return {
              isValid: false,
              field: `parts[${i}].geometry.cutouts[${c}]`,
              error: `${partPrefix} cutout #${c + 1} has invalid dimensions. Requires { x, y, w, h } with w > 0 and h > 0.`,
              suggestion: 'Set valid numbers: { x: 0, y: 10, w: 3.0, h: 12.0 }.'
            };
          }
        }
      }

      // Check 3D positioning
      if (!Array.isArray(part.assembledPos) || part.assembledPos.length < 3) {
        warnings.push(`${partPrefix} missing assembledPos [x, y, z]. Defaulting to [0, 0, 0].`);
      }

      // Check connections if defined
      if (Array.isArray(part.connections)) {
        for (const conn of part.connections) {
          if (conn.partId && !allPartIds.has(conn.partId)) {
            warnings.push(`${partPrefix} has connection referencing unknown part "${conn.partId}".`);
          }
        }
      }
    }

    return {
      isValid: true,
      warnings
    };
  }

  /**
   * Normalizes JavaScript runtime / syntax errors to extract line numbers and suggest actionable fixes.
   */
  static normalizeError(err, sourceCode) {
    const message = err.message || 'Unknown syntax error';
    let line = 1;
    let column = 1;

    // Try parsing stack / message for line numbers: e.g. "blob:http://...:14:25" or "line 14"
    const match = err.stack?.match(/:(\d+):(\d+)/) || message.match(/line (\d+)/i);
    if (match) {
      line = parseInt(match[1], 10);
      column = match[2] ? parseInt(match[2], 10) : 1;
    }

    let suggestion = 'Check for syntax errors such as missing commas, unmatched braces {}, or incorrect import statements.';

    if (message.includes('Unexpected token')) {
      suggestion = 'You might have a missing comma between properties or an unclosed brace/bracket.';
    } else if (message.includes('is not defined')) {
      suggestion = 'A variable was referenced before declaration. Ensure all helper functions or constants (e.g. THICKNESS) are declared.';
    } else if (message.includes('Cannot read properties of undefined')) {
      suggestion = 'Attempted to access a property on an undefined object. Verify that your arrays and objects are fully initialized.';
    }

    return {
      message,
      line,
      column,
      suggestion,
      rawError: err.toString()
    };
  }
}
