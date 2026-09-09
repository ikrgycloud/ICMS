const assert = require('assert/strict')
const fs = require('fs')
const Module = require('module')
const ts = require('typescript')

const filename = require.resolve('../src/views/rbacMatrix.ts')
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const sourceModule = new Module(filename)
sourceModule.filename = filename
sourceModule.paths = Module._nodeModulePaths(require('path').dirname(filename))
sourceModule._compile(compiled, filename)
const { parseRbacMatrix, rbacGrant, DENIED_RBAC_GRANT } = sourceModule.exports

const valid = parseRbacMatrix({ rows: [{ office: 'Dean — Academics', cells: { view: 'Full' } }], verbs: ['view'] })
assert.equal(rbacGrant(valid.rows[0], valid.verbs[0]), 'Full')

const missing = parseRbacMatrix({ rows: [{ office: 'Dean — Academics', cells: {} }], verbs: ['view'] })
assert.equal(rbacGrant(missing.rows[0], missing.verbs[0]), DENIED_RBAC_GRANT)

const malformed = parseRbacMatrix({ rows: [{ office: 'Dean — Academics', cells: null }], verbs: ['view', 'unknown'] })
assert.equal(rbacGrant(malformed.rows[0], 'view'), DENIED_RBAC_GRANT)
assert.equal(rbacGrant(malformed.rows[0], 'unknown'), DENIED_RBAC_GRANT)
console.log('RBAC matrix contract tests passed')
