// pd-ac-check-*: the five inert AC completion-contract check elements.
//   <pd-ac id="AC-1" …>
//     <pd-ac-check-command run="npm test" expect-exit="0" />
//     <pd-ac-check-output run="curl …" matches="429" />
//     <pd-ac-check-test report="junit.xml" name="returns 429" suite="rate" />
//     <pd-ac-check-file-exists path="src/limiter.ts" />
//     <pd-ac-check-file-contains path="README.md" pattern="rate limit" />
//   </pd-ac>
//
// Inert in this version (T1): the elements add NO DOM, inject NO visual
// treatment, compute NO status, fire NO events, and do not touch the parent
// `<pd-ac>`. They exist only to carry the author's check contract in the DOM,
// where agents/CLI read it. The frozen schema + parser live in ac-check-core.js
// (the single source of truth); the read-only `.check` accessor exposes the
// parsed check to in-browser callers. Status/rendering arrive in a later task.

import { PdElement, define } from './util.js';
import { parseAcCheck } from './ac-check-core.js';

class PdAcCheck extends PdElement {
  get check() { return parseAcCheck(this); }
}

// A custom element constructor may be registered against exactly one tag, so each
// tag gets a thin subclass. All behaviour (the inert no-op init + `.check`) lives
// on PdAcCheck; the subclasses add nothing.
class PdAcCheckCommand extends PdAcCheck {}
class PdAcCheckOutput extends PdAcCheck {}
class PdAcCheckTest extends PdAcCheck {}
class PdAcCheckFileExists extends PdAcCheck {}
class PdAcCheckFileContains extends PdAcCheck {}

define('pd-ac-check-command', PdAcCheckCommand);
define('pd-ac-check-output', PdAcCheckOutput);
define('pd-ac-check-test', PdAcCheckTest);
define('pd-ac-check-file-exists', PdAcCheckFileExists);
define('pd-ac-check-file-contains', PdAcCheckFileContains);
