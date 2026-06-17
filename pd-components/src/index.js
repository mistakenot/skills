// pd-components entry point. Bundled to a single classic (IIFE) script so it
// loads from file:// pages too (module scripts are CORS-blocked on file://).

import css from './styles.css';

import './doc.js';
import './threads.js';
import './files.js';
import './stepper.js';
import './mermaid.js';
import './code.js';
import './unit.js';
import './misc.js';
import './scope.js';
import './dag.js';
import './trace.js';
import './md.js';
import './mirror.js'; // auto-injects after component init
import './lint.js';   // last: derives consistency checks after components mount

const style = document.createElement('style');
style.dataset.pdComponents = __PD_VERSION__;
style.textContent = css;
document.head.append(style);
