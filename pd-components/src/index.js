// pd-components entry point. Bundled to a single classic (IIFE) script so it
// loads from file:// pages too (module scripts are CORS-blocked on file://).

import css from './styles.css';

import './doc.js';
import './threads.js';
import './files.js';
import './stepper.js';
import './mermaid.js';
import './code.js';
import './misc.js';
import './md.js';

const style = document.createElement('style');
style.dataset.pdComponents = __PD_VERSION__;
style.textContent = css;
document.head.append(style);
