const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const html = fs.readFileSync('index.html', 'utf8');
const roleCode = html.slice(html.indexOf('function applyRoleUIRestrictions()'), html.indexOf('// --- MODAL DE CONFIRMACIÓN'));
const tabCode = html.slice(html.indexOf('window.switchTab = function(tabId)'), html.indexOf('window.toggleSidebar = function'));
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set(['nav-btn', 'custom-marker']);
    elements.set(id, {classList: {add: (...items) => items.forEach(x => classes.add(x)), remove: (...items) => items.forEach(x => classes.delete(x)), contains: x => classes.has(x)}});
  }
  return elements.get(id);
}
const context = {window: {appState: {currentUserRole: 'admin'}}, document: {getElementById: element, querySelectorAll: selector => selector === '.nav-btn' ? [...elements.entries()].filter(([id]) => id.startsWith('btn-tab-')).map(([,el]) => el) : []}, renderDashboardStats() {}, renderSectorChart() {}, renderConflictsTab() {}, renderDiagnostics() {}};
vm.createContext(context);
vm.runInContext(roleCode + tabCode, context);
for (const role of ['admin', 'operador', 'admin']) {
  context.window.appState.currentUserRole = role;
  context.applyRoleUIRestrictions();
  assert.equal(element('btn-tab-errores').classList.contains('hidden'), role !== 'admin', 'initial visibility for ' + role);
  context.window.switchTab('usuarios');
  assert.equal(context.window.appState.currentTab, role === 'admin' ? 'usuarios' : 'dashboard');
  assert.equal(element('btn-tab-errores').classList.contains('hidden'), role !== 'admin', 'visibility after navigation for ' + role);
  assert.ok(element('btn-tab-errores').classList.contains('custom-marker'));
  context.window.switchTab('errores');
  assert.equal(context.window.appState.currentTab, role === 'admin' ? 'errores' : 'dashboard');
}
console.log('PASS admin initial visibility, operator restrictions, navigation and role changes');
