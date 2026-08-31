/* @ds-bundle: {"format":4,"namespace":"Plant360AIDesignSystem_796edf","components":[{"name":"Button","sourcePath":"components/actions/Button.jsx"},{"name":"IconButton","sourcePath":"components/actions/IconButton.jsx"},{"name":"DataTable","sourcePath":"components/data/DataTable.jsx"},{"name":"Pagination","sourcePath":"components/data/Pagination.jsx"},{"name":"Tag","sourcePath":"components/data/Tag.jsx"},{"name":"TAG_TYPES","sourcePath":"components/data/Tag.jsx"},{"name":"InlineNotification","sourcePath":"components/feedback/InlineNotification.jsx"},{"name":"Loading","sourcePath":"components/feedback/Loading.jsx"},{"name":"Modal","sourcePath":"components/feedback/Modal.jsx"},{"name":"ProgressBar","sourcePath":"components/feedback/ProgressBar.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"RadioButton","sourcePath":"components/forms/RadioButton.jsx"},{"name":"RadioButtonGroup","sourcePath":"components/forms/RadioButton.jsx"},{"name":"Search","sourcePath":"components/forms/Search.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"TextArea","sourcePath":"components/forms/TextArea.jsx"},{"name":"TextInput","sourcePath":"components/forms/TextInput.jsx"},{"name":"Toggle","sourcePath":"components/forms/Toggle.jsx"},{"name":"Icon","sourcePath":"components/icons/Icon.jsx"},{"name":"ICON_NAMES","sourcePath":"components/icons/Icon.jsx"},{"name":"Accordion","sourcePath":"components/layout/Accordion.jsx"},{"name":"Link","sourcePath":"components/layout/Link.jsx"},{"name":"OverflowMenu","sourcePath":"components/layout/OverflowMenu.jsx"},{"name":"Tile","sourcePath":"components/layout/Tile.jsx"},{"name":"Breadcrumb","sourcePath":"components/navigation/Breadcrumb.jsx"},{"name":"ContentSwitcher","sourcePath":"components/navigation/ContentSwitcher.jsx"},{"name":"Header","sourcePath":"components/navigation/Header.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/actions/Button.jsx":"ea4bd65761c0","components/actions/IconButton.jsx":"b56d8e7a84d9","components/data/DataTable.jsx":"b57832e8f05b","components/data/Pagination.jsx":"2a8cec4403dd","components/data/Tag.jsx":"aaa77e70396b","components/feedback/InlineNotification.jsx":"c203234c1052","components/feedback/Loading.jsx":"cdd0c71824f0","components/feedback/Modal.jsx":"f564e8437cb4","components/feedback/ProgressBar.jsx":"c122b6e236d9","components/feedback/Tooltip.jsx":"e2d492d07632","components/forms/Checkbox.jsx":"ffa12ff00b5b","components/forms/RadioButton.jsx":"2deb4bcf1cf2","components/forms/Search.jsx":"0a48f287733c","components/forms/Select.jsx":"1efdd90a31db","components/forms/TextArea.jsx":"ad22a8e598d6","components/forms/TextInput.jsx":"b0055686cb3e","components/forms/Toggle.jsx":"a78eacabe902","components/icons/Icon.jsx":"fbaf6419f772","components/layout/Accordion.jsx":"d9c252585159","components/layout/Link.jsx":"3b09fc411de8","components/layout/OverflowMenu.jsx":"1fac6f52b747","components/layout/Tile.jsx":"90243afd9694","components/navigation/Breadcrumb.jsx":"08831172baaf","components/navigation/ContentSwitcher.jsx":"19eee29201c4","components/navigation/Header.jsx":"da59554605ed","components/navigation/Tabs.jsx":"cb0e0e575ebe","ui_kits/plant360-console/screens.jsx":"835b1c8ff4d4"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.Plant360AIDesignSystem_796edf = window.Plant360AIDesignSystem_796edf || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/data/DataTable.jsx
try { (() => {
const DT_CSS = `
.p360--data-table { inline-size: 100%; border-collapse: collapse; border-spacing: 0; }
.p360--data-table thead { background: var(--layer-accent-01); }
.p360--data-table th { padding: 0 var(--spacing-05); text-align: left; color: var(--text-primary); font-size: var(--heading-compact-01-size); line-height: var(--heading-compact-01-lh); letter-spacing: 0.16px; font-weight: var(--font-weight-semibold); vertical-align: middle; }
.p360--data-table--lg th, .p360--data-table--lg td { block-size: 3rem; }
.p360--data-table--md th, .p360--data-table--md td { block-size: 2.5rem; }
.p360--data-table--sm th, .p360--data-table--sm td { block-size: 2rem; }
.p360--data-table tbody tr { background: var(--layer-01); border-block-start: 1px solid var(--layer-accent-01); transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--data-table tbody tr:hover { background: var(--layer-hover-01); }
.p360--data-table td { padding: 0 var(--spacing-05); color: var(--text-secondary); font-size: var(--body-compact-01-size); line-height: var(--body-compact-01-lh); letter-spacing: 0.16px; vertical-align: middle; border: 0; }
.p360--data-table tbody tr:first-child { border-block-start: 0; }
.p360--data-table--zebra tbody tr:nth-child(even) { background: var(--layer-02); }
.p360--data-table__title { margin: 0; color: var(--text-primary); font-size: var(--heading-03-size); line-height: var(--heading-03-lh); font-weight: var(--font-weight-regular); }
.p360--data-table__description { margin: var(--spacing-02) 0 0; color: var(--text-secondary); font-size: var(--body-compact-01-size); }
.p360--data-table__header { padding: var(--spacing-05) var(--spacing-05) var(--spacing-06); background: var(--layer-01); }
.p360--data-table__container { inline-size: 100%; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function DataTable({
  headers = [],
  rows = [],
  size = 'lg',
  zebra,
  title,
  description,
  className = ''
}) {
  ensureCss('p360-dt-css', DT_CSS);
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--data-table__container ' + className).trim()
  }, title ? /*#__PURE__*/React.createElement("div", {
    className: "p360--data-table__header"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "p360--data-table__title"
  }, title), description ? /*#__PURE__*/React.createElement("p", {
    className: "p360--data-table__description"
  }, description) : null) : null, /*#__PURE__*/React.createElement("table", {
    className: ['p360--data-table', 'p360--data-table--' + size, zebra ? 'p360--data-table--zebra' : ''].filter(Boolean).join(' ')
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, headers.map((h, i) => /*#__PURE__*/React.createElement("th", {
    key: i,
    scope: "col"
  }, h)))), /*#__PURE__*/React.createElement("tbody", null, rows.map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, r.map((cell, j) => /*#__PURE__*/React.createElement("td", {
    key: j
  }, cell)))))));
}
Object.assign(__ds_scope, { DataTable });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DataTable.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Loading.jsx
try { (() => {
const LD_CSS = `
@keyframes p360-rotate { 100% { transform: rotate(360deg); } }
.p360--loading { display: inline-block; animation: p360-rotate 690ms linear infinite; }
.p360--loading circle { stroke: var(--interactive); stroke-dasharray: 240; stroke-dashoffset: 40; fill: none; }
.p360--loading--small circle { stroke-dasharray: 150; stroke-dashoffset: 20; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Loading({
  small,
  size,
  description = 'Loading',
  className = ''
}) {
  ensureCss('p360-ld-css', LD_CSS);
  const px = size || (small ? 16 : 88);
  return /*#__PURE__*/React.createElement("svg", {
    className: ['p360--loading', small ? 'p360--loading--small' : '', className].filter(Boolean).join(' '),
    viewBox: "0 0 100 100",
    width: px,
    height: px,
    role: "img",
    "aria-label": description
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "50",
    cy: "50",
    r: "44",
    strokeWidth: small ? 12 : 8
  }));
}
Object.assign(__ds_scope, { Loading });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Loading.jsx", error: String((e && e.message) || e) }); }

// components/feedback/ProgressBar.jsx
try { (() => {
const PB_CSS = `
.p360--progress-bar { inline-size: 100%; }
.p360--progress-bar__label { display: block; margin-block-end: var(--spacing-03); color: var(--text-primary); font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; }
.p360--progress-bar__track { position: relative; inline-size: 100%; block-size: 0.5rem; background: var(--layer-accent-01); overflow: hidden; }
.p360--progress-bar--small .p360--progress-bar__track { block-size: 0.25rem; }
.p360--progress-bar__fill { block-size: 100%; background: var(--interactive); transition: width var(--duration-moderate-01) var(--easing-standard-productive); }
.p360--progress-bar--error .p360--progress-bar__fill { background: var(--support-error); }
.p360--progress-bar--success .p360--progress-bar__fill { background: var(--support-success); }
.p360--progress-bar__helper { margin-block-start: var(--spacing-03); color: var(--text-helper); font-size: var(--helper-text-01-size); letter-spacing: 0.32px; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function ProgressBar({
  label,
  helperText,
  value = 0,
  max = 100,
  size = 'big',
  status = 'active',
  className = ''
}) {
  ensureCss('p360-pb-css', PB_CSS);
  const pct = Math.min(100, Math.max(0, value / max * 100));
  return /*#__PURE__*/React.createElement("div", {
    className: ['p360--progress-bar', size === 'small' ? 'p360--progress-bar--small' : '', status !== 'active' ? 'p360--progress-bar--' + status : '', className].filter(Boolean).join(' ')
  }, label ? /*#__PURE__*/React.createElement("span", {
    className: "p360--progress-bar__label"
  }, label) : null, /*#__PURE__*/React.createElement("div", {
    className: "p360--progress-bar__track",
    role: "progressbar",
    "aria-valuenow": value,
    "aria-valuemax": max
  }, /*#__PURE__*/React.createElement("div", {
    className: "p360--progress-bar__fill",
    style: {
      width: pct + '%'
    }
  })), helperText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--progress-bar__helper"
  }, helperText) : null);
}
Object.assign(__ds_scope, { ProgressBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/ProgressBar.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
const {
  useState
} = React;
const TT_CSS = `
.p360--tooltip-wrap { position: relative; display: inline-flex; }
.p360--tooltip { position: absolute; z-index: 6000; inset-inline-start: 50%; transform: translateX(-50%); max-inline-size: 18rem; padding: var(--spacing-03) var(--spacing-05); border-radius: 2px; background: var(--background-inverse); color: var(--text-inverse); font-size: var(--body-compact-01-size); line-height: var(--body-compact-01-lh); letter-spacing: 0.16px; white-space: normal; width: max-content; pointer-events: none; opacity: 0; transition: opacity var(--duration-fast-01) var(--easing-standard-productive); }
.p360--tooltip--visible { opacity: 1; }
.p360--tooltip--top { inset-block-end: calc(100% + 8px); }
.p360--tooltip--bottom { inset-block-start: calc(100% + 8px); }
.p360--tooltip__caret { position: absolute; inset-inline-start: 50%; transform: translateX(-50%); border: 4px solid transparent; }
.p360--tooltip--top .p360--tooltip__caret { inset-block-start: 100%; border-block-start-color: var(--background-inverse); }
.p360--tooltip--bottom .p360--tooltip__caret { inset-block-end: 100%; border-block-end-color: var(--background-inverse); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Tooltip({
  label,
  align = 'top',
  children,
  className = ''
}) {
  ensureCss('p360-tt-css', TT_CSS);
  const [show, setShow] = useState(false);
  return /*#__PURE__*/React.createElement("span", {
    className: ('p360--tooltip-wrap ' + className).trim(),
    onMouseEnter: () => setShow(true),
    onMouseLeave: () => setShow(false),
    onFocus: () => setShow(true),
    onBlur: () => setShow(false)
  }, children, /*#__PURE__*/React.createElement("span", {
    className: ['p360--tooltip', 'p360--tooltip--' + align, show ? 'p360--tooltip--visible' : ''].filter(Boolean).join(' '),
    role: "tooltip"
  }, label, /*#__PURE__*/React.createElement("span", {
    className: "p360--tooltip__caret"
  })));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
const CB_CSS = `
.p360--checkbox-wrapper { position: relative; display: flex; align-items: center; min-block-size: 1.5rem; }
.p360--checkbox { position: absolute; opacity: 0; inline-size: 1rem; block-size: 1rem; margin: 0; }
.p360--checkbox-label { display: flex; align-items: center; gap: var(--spacing-03); cursor: pointer; color: var(--text-primary); font-size: var(--body-compact-01-size); line-height: var(--body-compact-01-lh); letter-spacing: 0.16px; user-select: none; }
.p360--checkbox-box { box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; inline-size: 1rem; block-size: 1rem; border: 1px solid var(--icon-primary); border-radius: 1px; background: transparent; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--checkbox:checked + .p360--checkbox-label .p360--checkbox-box,
.p360--checkbox:indeterminate + .p360--checkbox-label .p360--checkbox-box { background: var(--icon-primary); border-color: var(--icon-primary); }
.p360--checkbox:focus + .p360--checkbox-label .p360--checkbox-box { outline: 2px solid var(--focus); outline-offset: 1px; }
.p360--checkbox[disabled] + .p360--checkbox-label { color: var(--text-disabled); cursor: not-allowed; }
.p360--checkbox[disabled] + .p360--checkbox-label .p360--checkbox-box { border-color: var(--text-disabled); }
.p360--checkbox-tick { display: none; }
.p360--checkbox:checked + .p360--checkbox-label .p360--checkbox-tick--check { display: block; }
.p360--checkbox:indeterminate + .p360--checkbox-label .p360--checkbox-tick--dash { display: block; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Checkbox({
  labelText,
  checked,
  defaultChecked,
  indeterminate,
  disabled,
  onChange,
  id,
  className = ''
}) {
  ensureCss('p360-cb-css', CB_CSS);
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (ref.current) ref.current.indeterminate = !!indeterminate;
  }, [indeterminate]);
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--checkbox-wrapper ' + className).trim()
  }, /*#__PURE__*/React.createElement("input", {
    ref: ref,
    type: "checkbox",
    className: "p360--checkbox",
    id: id,
    checked: checked,
    defaultChecked: defaultChecked,
    disabled: disabled,
    onChange: onChange
  }), /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    className: "p360--checkbox-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--checkbox-box"
  }, /*#__PURE__*/React.createElement("svg", {
    className: "p360--checkbox-tick p360--checkbox-tick--check",
    width: "10",
    height: "8",
    viewBox: "0 0 10 8",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M1 4L3.5 6.5L9 1",
    stroke: "var(--icon-inverse)",
    strokeWidth: "1.8"
  })), /*#__PURE__*/React.createElement("svg", {
    className: "p360--checkbox-tick p360--checkbox-tick--dash",
    width: "8",
    height: "2",
    viewBox: "0 0 8 2"
  }, /*#__PURE__*/React.createElement("rect", {
    width: "8",
    height: "2",
    fill: "var(--icon-inverse)"
  }))), labelText));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/RadioButton.jsx
try { (() => {
const RB_CSS = `
.p360--radio-group { display: flex; flex-direction: column; gap: var(--spacing-03); }
.p360--radio-group--horizontal { flex-direction: row; gap: var(--spacing-05); }
.p360--radio-group__label { display: block; margin-block-end: var(--spacing-03); color: var(--text-secondary); font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; }
.p360--radio-wrapper { display: flex; align-items: center; }
.p360--radio { position: absolute; opacity: 0; }
.p360--radio-label { display: flex; align-items: center; gap: var(--spacing-03); cursor: pointer; color: var(--text-primary); font-size: var(--body-compact-01-size); letter-spacing: 0.16px; user-select: none; }
.p360--radio-circle { box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; inline-size: 1.125rem; block-size: 1.125rem; border: 1px solid var(--icon-primary); border-radius: 50%; }
.p360--radio-dot { inline-size: 0.5rem; block-size: 0.5rem; border-radius: 50%; background: var(--icon-primary); transform: scale(0); transition: transform var(--duration-fast-01) var(--easing-standard-productive); }
.p360--radio:checked + .p360--radio-label .p360--radio-dot { transform: scale(1); }
.p360--radio:focus + .p360--radio-label .p360--radio-circle { outline: 2px solid var(--focus); outline-offset: 1.5px; }
.p360--radio[disabled] + .p360--radio-label { color: var(--text-disabled); cursor: not-allowed; }
.p360--radio[disabled] + .p360--radio-label .p360--radio-circle { border-color: var(--text-disabled); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function RadioButton({
  labelText,
  name,
  value,
  checked,
  defaultChecked,
  disabled,
  onChange,
  id,
  className = ''
}) {
  ensureCss('p360-rb-css', RB_CSS);
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--radio-wrapper ' + className).trim()
  }, /*#__PURE__*/React.createElement("input", {
    type: "radio",
    className: "p360--radio",
    id: id,
    name: name,
    value: value,
    checked: checked,
    defaultChecked: defaultChecked,
    disabled: disabled,
    onChange: onChange
  }), /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    className: "p360--radio-label"
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--radio-circle"
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--radio-dot"
  })), labelText));
}
function RadioButtonGroup({
  legendText,
  orientation = 'horizontal',
  children,
  className = ''
}) {
  ensureCss('p360-rb-css', RB_CSS);
  return /*#__PURE__*/React.createElement("fieldset", {
    style: {
      border: 0,
      padding: 0,
      margin: 0
    },
    className: className
  }, legendText ? /*#__PURE__*/React.createElement("legend", {
    className: "p360--radio-group__label"
  }, legendText) : null, /*#__PURE__*/React.createElement("div", {
    className: 'p360--radio-group' + (orientation === 'horizontal' ? ' p360--radio-group--horizontal' : '')
  }, children));
}
Object.assign(__ds_scope, { RadioButton, RadioButtonGroup });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/RadioButton.jsx", error: String((e && e.message) || e) }); }

// components/forms/TextArea.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TA_CSS = `
.p360--form-item { display: flex; flex-direction: column; align-items: flex-start; inline-size: 100%; }
.p360--label { display: inline-block; margin-block-end: var(--spacing-03); color: var(--text-secondary); font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; font-weight: var(--font-weight-regular); }
.p360--label--disabled { color: var(--text-disabled); }
.p360--form__helper-text { margin-block-start: var(--spacing-02); color: var(--text-helper); font-size: var(--helper-text-01-size); line-height: var(--helper-text-01-lh); letter-spacing: 0.32px; }
.p360--form-requirement { margin-block-start: var(--spacing-02); color: var(--text-error); font-size: var(--helper-text-01-size); line-height: var(--helper-text-01-lh); letter-spacing: 0.32px; }

.p360--text-area { box-sizing: border-box; inline-size: 100%; min-block-size: 5rem; padding: 0.6875rem var(--spacing-05); border: none; border-block-end: 1px solid var(--border-strong-01); border-radius: 0; background: var(--field-01); color: var(--text-primary); font-family: inherit; font-size: var(--body-01-size); line-height: var(--body-01-lh); letter-spacing: 0.16px; outline: none; resize: vertical; }
.p360--text-area::placeholder { color: var(--text-placeholder); opacity: 1; }
.p360--text-area:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--text-area--invalid { outline: 2px solid var(--support-error); outline-offset: -2px; }
.p360--text-area[disabled] { border-block-end-color: transparent; color: var(--text-disabled); cursor: not-allowed; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function TextArea({
  labelText,
  helperText,
  invalid,
  invalidText,
  disabled,
  placeholder,
  rows = 4,
  className = '',
  id,
  ...rest
}) {
  ensureCss('p360-ta-css', TA_CSS);
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--form-item ' + className).trim()
  }, labelText ? /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    className: 'p360--label' + (disabled ? ' p360--label--disabled' : '')
  }, labelText) : null, /*#__PURE__*/React.createElement("textarea", _extends({
    id: id,
    rows: rows,
    className: 'p360--text-area' + (invalid ? ' p360--text-area--invalid' : ''),
    placeholder: placeholder,
    disabled: disabled
  }, rest)), invalid && invalidText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--form-requirement"
  }, invalidText) : helperText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--form__helper-text"
  }, helperText) : null);
}
Object.assign(__ds_scope, { TextArea });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/TextArea.jsx", error: String((e && e.message) || e) }); }

// components/forms/Toggle.jsx
try { (() => {
const {
  useState
} = React;
const TG_CSS = `
.p360--toggle { display: flex; flex-direction: column; gap: var(--spacing-03); }
.p360--toggle__label { color: var(--text-secondary); font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; }
.p360--toggle__row { display: flex; align-items: center; gap: var(--spacing-03); }
.p360--toggle__button { position: relative; box-sizing: border-box; inline-size: 3rem; block-size: 1.5rem; padding: 0; border: 0; border-radius: 0.75rem; background: var(--toggle-off); cursor: pointer; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--toggle__button--sm { inline-size: 2rem; block-size: 1rem; border-radius: 0.5rem; }
.p360--toggle__button:focus { outline: 2px solid var(--focus); outline-offset: 1px; }
.p360--toggle__button--on { background: var(--support-success); }
.p360--toggle__handle { position: absolute; inset-block-start: 3px; inset-inline-start: 3px; inline-size: 1.125rem; block-size: 1.125rem; border-radius: 50%; background: var(--icon-on-color); transition: transform var(--duration-fast-01) var(--easing-standard-productive); }
.p360--toggle__button--sm .p360--toggle__handle { inline-size: 0.625rem; block-size: 0.625rem; }
.p360--toggle__button--on .p360--toggle__handle { transform: translateX(1.5rem); }
.p360--toggle__button--sm.p360--toggle__button--on .p360--toggle__handle { transform: translateX(1rem); }
.p360--toggle__text { color: var(--text-primary); font-size: var(--body-compact-01-size); letter-spacing: 0.16px; }
.p360--toggle__button[disabled] { background: var(--button-disabled); cursor: not-allowed; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Toggle({
  labelText,
  labelA = 'Off',
  labelB = 'On',
  size = 'md',
  defaultToggled = false,
  toggled,
  onToggle,
  disabled,
  id,
  className = ''
}) {
  ensureCss('p360-tg-css', TG_CSS);
  const [internal, setInternal] = useState(defaultToggled);
  const isOn = toggled !== undefined ? toggled : internal;
  const flip = () => {
    if (disabled) return;
    const v = !isOn;
    if (toggled === undefined) setInternal(v);
    onToggle && onToggle(v);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--toggle ' + className).trim()
  }, labelText ? /*#__PURE__*/React.createElement("span", {
    className: "p360--toggle__label"
  }, labelText) : null, /*#__PURE__*/React.createElement("div", {
    className: "p360--toggle__row"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    id: id,
    role: "switch",
    "aria-checked": isOn,
    disabled: disabled,
    className: ['p360--toggle__button', size === 'sm' ? 'p360--toggle__button--sm' : '', isOn ? 'p360--toggle__button--on' : ''].filter(Boolean).join(' '),
    onClick: flip
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--toggle__handle"
  })), /*#__PURE__*/React.createElement("span", {
    className: "p360--toggle__text"
  }, isOn ? labelB : labelA)));
}
Object.assign(__ds_scope, { Toggle });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Toggle.jsx", error: String((e && e.message) || e) }); }

// components/icons/Icon.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// Carbon system icons — path data copied verbatim from carbon-design-system/carbon packages/icons/src/svg/32
const ICONS = {
  "add": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "17,15 17,8 15,8 15,15 8,15 8,17 15,17 15,24 17,24 17,17 24,17 24,15 "
  }), " "),
  "analytics": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M4,2H2V28a2,2,0,0,0,2,2H30V28H4Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M30,9H23v2h3.59L19,18.59l-4.29-4.3a1,1,0,0,0-1.42,0L6,21.59,7.41,23,14,16.41l4.29,4.3a1,1,0,0,0,1.42,0L28,12.41V16h2Z"
  })),
  "arrow--left": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "14 26 15.41 24.59 7.83 17 28 17 28 15 7.83 15 15.41 7.41 14 6 4 16 14 26"
  })),
  "arrow--right": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "18 6 16.57 7.393 24.15 15 4 15 4 17 24.15 17 16.57 24.573 18 26 28 16 18 6"
  })),
  "calendar": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M26,4h-4V2h-2v2h-8V2h-2v2H6C4.9,4,4,4.9,4,6v20c0,1.1,0.9,2,2,2h20c1.1,0,2-0.9,2-2V6C28,4.9,27.1,4,26,4z M26,26H6V12h20 V26z M26,10H6V6h4v2h2V6h8v2h2V6h4V10z"
  })),
  "checkmark--filled": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,2A14,14,0,1,0,30,16,14,14,0,0,0,16,2ZM14,21.5908l-5-5L10.5906,15,14,18.4092,21.41,11l1.5957,1.5859Z"
  }), "   ", /*#__PURE__*/React.createElement("polygon", {
    id: "inner-path",
    points: "14 21.591 9 16.591 10.591 15 14 18.409 21.41 11 23.005 12.585 14 21.591",
    fill: "none"
  })),
  "checkmark": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "13 24 4 15 5.414 13.586 13 21.171 26.586 7.586 28 9 13 24"
  })),
  "chevron--down": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "16,22 6,12 7.4,10.6 16,19.2 24.6,10.6 26,12 "
  })),
  "chevron--left": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "10,16 20,6 21.4,7.4 12.8,16 21.4,24.6 20,26 "
  })),
  "chevron--right": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "22,16 12,26 10.6,24.6 19.2,16 10.6,7.4 12,6 "
  })),
  "chevron--up": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "16,10 26,20 24.6,21.4 16,12.8 7.4,21.4 6,20 "
  })),
  "close": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("polygon", {
    points: "17.4141 16 24 9.4141 22.5859 8 16 14.5859 9.4143 8 8 9.4141 14.5859 16 8 22.5859 9.4143 24 16 17.4141 22.5859 24 24 22.5859 17.4141 16"
  }), "   "),
  "dashboard": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
    x: "24",
    y: "21",
    width: "2",
    height: "5"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "20",
    y: "16",
    width: "2",
    height: "10"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M11,26a5.0059,5.0059,0,0,1-5-5H8a3,3,0,1,0,3-3V16a5,5,0,0,1,0,10Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M28,2H4A2.002,2.002,0,0,0,2,4V28a2.0023,2.0023,0,0,0,2,2H28a2.0027,2.0027,0,0,0,2-2V4A2.0023,2.0023,0,0,0,28,2Zm0,9H14V4H28ZM12,4v7H4V4ZM4,28V13H28.0007l.0013,15Z"
  })),
  "download": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M26,24v4H6V24H4v4H4a2,2,0,0,0,2,2H26a2,2,0,0,0,2-2h0V24Z"
  }), "   ", /*#__PURE__*/React.createElement("polygon", {
    points: "26 14 24.59 12.59 17 20.17 17 2 15 2 15 20.17 7.41 12.59 6 14 16 24 26 14"
  }), "   "),
  "edit": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "26",
    width: "28",
    height: "2"
  }), " ", /*#__PURE__*/React.createElement("path", {
    d: "M25.4,9c0.8-0.8,0.8-2,0-2.8c0,0,0,0,0,0l-3.6-3.6c-0.8-0.8-2-0.8-2.8,0c0,0,0,0,0,0l-15,15V24h6.4L25.4,9z M20.4,4L24,7.6 l-3,3L17.4,7L20.4,4z M6,22v-3.6l10-10l3.6,3.6l-10,10H6z"
  })),
  "error--filled": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,2A13.914,13.914,0,0,0,2,16,13.914,13.914,0,0,0,16,30,13.914,13.914,0,0,0,30,16,13.914,13.914,0,0,0,16,2Zm5.4449,21L9,10.5557,10.5557,9,23,21.4448Z"
  })),
  "filter": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M18,28H14a2,2,0,0,1-2-2V18.41L4.59,11A2,2,0,0,1,4,9.59V6A2,2,0,0,1,6,4H26a2,2,0,0,1,2,2V9.59A2,2,0,0,1,27.41,11L20,18.41V26A2,2,0,0,1,18,28ZM6,6V9.59l8,8V26h4V17.59l8-8V6Z"
  })),
  "growth": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M20,8v2h6.5859L18,18.5859,13.707,14.293a.9994.9994,0,0,0-1.414,0L2,24.5859,3.4141,26,13,16.4141l4.293,4.2929a.9994.9994,0,0,0,1.414,0L28,11.4141V18h2V8Z"
  })),
  "help": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,2A14,14,0,1,0,30,16,14,14,0,0,0,16,2Zm0,26A12,12,0,1,1,28,16,12,12,0,0,1,16,28Z"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "16",
    cy: "23.5",
    r: "1.5"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M17,8H15.5A4.49,4.49,0,0,0,11,12.5V13h2v-.5A2.5,2.5,0,0,1,15.5,10H17a2.5,2.5,0,0,1,0,5H15v4.5h2V17a4.5,4.5,0,0,0,0-9Z"
  })),
  "humidity": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M23.4761,13.9932,16.8472,3.4365a1.04,1.04,0,0,0-1.6944,0L8.4941,14.0444A9.9861,9.9861,0,0,0,7,19a9,9,0,0,0,18,0A10.0632,10.0632,0,0,0,23.4761,13.9932ZM16,26.0005a7.0089,7.0089,0,0,1-7-7,7.978,7.978,0,0,1,1.2183-3.9438l.935-1.4888L21.2271,23.6411A6.9772,6.9772,0,0,1,16,26.0005Z"
  })),
  "information--filled": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,2A14,14,0,1,0,30,16,14,14,0,0,0,16,2Zm0,6a1.5,1.5,0,1,1-1.5,1.5A1.5,1.5,0,0,1,16,8Zm4,16.125H12v-2.25h2.875v-5.75H13v-2.25h4.125v8H20Z",
    transform: "translate(0 0)"
  })),
  "launch": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M26,28H6a2.0027,2.0027,0,0,1-2-2V6A2.0027,2.0027,0,0,1,6,4H16V6H6V26H26V16h2V26A2.0027,2.0027,0,0,1,26,28Z"
  }), "   ", /*#__PURE__*/React.createElement("polygon", {
    points: "20 2 20 4 26.586 4 18 12.586 19.414 14 28 5.414 28 12 30 12 30 2 20 2"
  })),
  "location": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,18a5,5,0,1,1,5-5A5.0057,5.0057,0,0,1,16,18Zm0-8a3,3,0,1,0,3,3A3.0033,3.0033,0,0,0,16,10Z"
  }), "   ", /*#__PURE__*/React.createElement("path", {
    d: "M16,30,7.5645,20.0513c-.0479-.0571-.3482-.4515-.3482-.4515A10.8888,10.8888,0,0,1,5,13a11,11,0,0,1,22,0,10.8844,10.8844,0,0,1-2.2148,6.5973l-.0015.0025s-.3.3944-.3447.4474ZM8.8125,18.395c.001.0007.2334.3082.2866.3744L16,26.9079l6.91-8.15c.0439-.0552.2783-.3649.2788-.3657A8.901,8.901,0,0,0,25,13,9,9,0,1,0,7,13a8.9054,8.9054,0,0,0,1.8125,5.395Z"
  })),
  "logout": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M6,30H18a2.0023,2.0023,0,0,0,2-2V25H18v3H6V4H18V7h2V4a2.0023,2.0023,0,0,0-2-2H6A2.0023,2.0023,0,0,0,4,4V28A2.0023,2.0023,0,0,0,6,30Z"
  }), /*#__PURE__*/React.createElement("polygon", {
    points: "20.586 20.586 24.172 17 10 17 10 15 24.172 15 20.586 11.414 22 10 28 16 22 22 20.586 20.586"
  })),
  "map": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,24l-6.09-8.6A8.14,8.14,0,0,1,16,2a8.08,8.08,0,0,1,8,8.13,8.2,8.2,0,0,1-1.8,5.13ZM16,4a6.07,6.07,0,0,0-6,6.13,6.19,6.19,0,0,0,1.49,4L16,20.52,20.63,14A6.24,6.24,0,0,0,22,10.13,6.07,6.07,0,0,0,16,4Z",
    transform: "translate(0 0)"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "16",
    cy: "9",
    r: "2"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M28,12H26v2h2V28H4V14H6V12H4a2,2,0,0,0-2,2V28a2,2,0,0,0,2,2H28a2,2,0,0,0,2-2V14A2,2,0,0,0,28,12Z",
    transform: "translate(0 0)"
  })),
  "menu": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "6",
    width: "24",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "24",
    width: "24",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "12",
    width: "24",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "18",
    width: "24",
    height: "2"
  })),
  "notification": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M28.7071,19.293,26,16.5859V13a10.0136,10.0136,0,0,0-9-9.9492V1H15V3.0508A10.0136,10.0136,0,0,0,6,13v3.5859L3.2929,19.293A1,1,0,0,0,3,20v3a1,1,0,0,0,1,1h7v.7768a5.152,5.152,0,0,0,4.5,5.1987A5.0057,5.0057,0,0,0,21,25V24h7a1,1,0,0,0,1-1V20A1,1,0,0,0,28.7071,19.293ZM19,25a3,3,0,0,1-6,0V24h6Zm8-3H5V20.4141L7.707,17.707A1,1,0,0,0,8,17V13a8,8,0,0,1,16,0v4a1,1,0,0,0,.293.707L27,20.4141Z"
  })),
  "overflow-menu--vertical": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
    cx: "16",
    cy: "8",
    r: "2"
  }), " ", /*#__PURE__*/React.createElement("circle", {
    cx: "16",
    cy: "16",
    r: "2"
  }), " ", /*#__PURE__*/React.createElement("circle", {
    cx: "16",
    cy: "24",
    r: "2"
  })),
  "rain": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M23.5,22H8.5A6.5,6.5,0,0,1,7.2,9.14a9,9,0,0,1,17.6,0A6.5,6.5,0,0,1,23.5,22ZM16,4a7,7,0,0,0-6.94,6.14L9,11,8.14,11a4.5,4.5,0,0,0,.36,9h15a4.5,4.5,0,0,0,.36-9L23,11l-.1-.82A7,7,0,0,0,16,4Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M14,30a.93.93,0,0,1-.45-.11,1,1,0,0,1-.44-1.34l2-4a1,1,0,1,1,1.78.9l-2,4A1,1,0,0,1,14,30Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M20,30a.93.93,0,0,1-.45-.11,1,1,0,0,1-.44-1.34l2-4a1,1,0,1,1,1.78.9l-2,4A1,1,0,0,1,20,30Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M8,30a.93.93,0,0,1-.45-.11,1,1,0,0,1-.44-1.34l2-4a1,1,0,1,1,1.78.9l-2,4A1,1,0,0,1,8,30Z"
  })),
  "renew": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M12,10H6.78A11,11,0,0,1,27,16h2A13,13,0,0,0,6,7.68V4H4v8h8Z"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M20,22h5.22A11,11,0,0,1,5,16H3a13,13,0,0,0,23,8.32V28h2V20H20Z"
  })),
  "search": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M29,27.5859l-7.5521-7.5521a11.0177,11.0177,0,1,0-1.4141,1.4141L27.5859,29ZM4,13a9,9,0,1,1,9,9A9.01,9.01,0,0,1,4,13Z",
    transform: "translate(0 0)"
  })),
  "settings": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M27,16.76c0-.25,0-.5,0-.76s0-.51,0-.77l1.92-1.68A2,2,0,0,0,29.3,11L26.94,7a2,2,0,0,0-1.73-1,2,2,0,0,0-.64.1l-2.43.82a11.35,11.35,0,0,0-1.31-.75l-.51-2.52a2,2,0,0,0-2-1.61H13.64a2,2,0,0,0-2,1.61l-.51,2.52a11.48,11.48,0,0,0-1.32.75L7.43,6.06A2,2,0,0,0,6.79,6,2,2,0,0,0,5.06,7L2.7,11a2,2,0,0,0,.41,2.51L5,15.24c0,.25,0,.5,0,.76s0,.51,0,.77L3.11,18.45A2,2,0,0,0,2.7,21L5.06,25a2,2,0,0,0,1.73,1,2,2,0,0,0,.64-.1l2.43-.82a11.35,11.35,0,0,0,1.31.75l.51,2.52a2,2,0,0,0,2,1.61h4.72a2,2,0,0,0,2-1.61l.51-2.52a11.48,11.48,0,0,0,1.32-.75l2.42.82a2,2,0,0,0,.64.1,2,2,0,0,0,1.73-1L29.3,21a2,2,0,0,0-.41-2.51ZM25.21,24l-3.43-1.16a8.86,8.86,0,0,1-2.71,1.57L18.36,28H13.64l-.71-3.55a9.36,9.36,0,0,1-2.7-1.57L6.79,24,4.43,20l2.72-2.4a8.9,8.9,0,0,1,0-3.13L4.43,12,6.79,8l3.43,1.16a8.86,8.86,0,0,1,2.71-1.57L13.64,4h4.72l.71,3.55a9.36,9.36,0,0,1,2.7,1.57L25.21,8,27.57,12l-2.72,2.4a8.9,8.9,0,0,1,0,3.13L27.57,20Z",
    transform: "translate(0 0)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M16,22a6,6,0,1,1,6-6A5.94,5.94,0,0,1,16,22Zm0-10a3.91,3.91,0,0,0-4,4,3.91,3.91,0,0,0,4,4,3.91,3.91,0,0,0,4-4A3.91,3.91,0,0,0,16,12Z",
    transform: "translate(0 0)"
  })),
  "sprout": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M25,2A11.01,11.01,0,0,0,14.7549,9.0244,6.9939,6.9939,0,0,0,9,6H6V9a7.0078,7.0078,0,0,0,7,7h1v9.0493a9.9229,9.9229,0,0,0-6.071,2.8794l1.414,1.4141a8,8,0,0,1,12.3086,1.2134l1.6616-1.1128A9.98,9.98,0,0,0,16,25.062V16h1A11.0125,11.0125,0,0,0,28,5V2ZM13,14A5.0057,5.0057,0,0,1,8,9V8H9a5.0054,5.0054,0,0,1,5,5v1ZM26,5a9.01,9.01,0,0,1-9,9H16V13a9.01,9.01,0,0,1,9-9h1Z"
  })),
  "subtract": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
    x: "8",
    y: "15",
    width: "16",
    height: "2"
  })),
  "sun": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,12a4,4,0,1,1-4,4,4.0045,4.0045,0,0,1,4-4m0-2a6,6,0,1,0,6,6,6,6,0,0,0-6-6Z",
    transform: "translate(0 0.0049)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "6.8536",
    y: "5.3745",
    width: "1.9998",
    height: "4.958",
    transform: "translate(-3.253 7.8584) rotate(-45)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "15.0049",
    width: "5",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "5.3745",
    y: "23.1466",
    width: "4.958",
    height: "1.9998",
    transform: "translate(-14.7739 12.6305) rotate(-45)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "15",
    y: "25.0049",
    width: "2",
    height: "5"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "23.1466",
    y: "21.6675",
    width: "1.9998",
    height: "4.958",
    transform: "translate(-10.0018 24.1514) rotate(-45)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "25",
    y: "15.0049",
    width: "5",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "21.6675",
    y: "6.8536",
    width: "4.958",
    height: "1.9998",
    transform: "translate(1.5191 19.3793) rotate(-45)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "15",
    y: "2.0049",
    width: "2",
    height: "5"
  })),
  "temperature": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M13,17.26V6A4,4,0,0,0,5,6V17.26a7,7,0,1,0,8,0ZM9,4a2,2,0,0,1,2,2v7H7V6A2,2,0,0,1,9,4ZM9,28a5,5,0,0,1-2.5-9.33l.5-.28V15h4v3.39l.5.28A5,5,0,0,1,9,28Z",
    transform: "translate(0 0)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "20",
    y: "4",
    width: "10",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "20",
    y: "10",
    width: "7",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "20",
    y: "16",
    width: "10",
    height: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "20",
    y: "22",
    width: "7",
    height: "2"
  })),
  "trash-can": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("rect", {
    x: "12",
    y: "12",
    width: "2",
    height: "12"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "18",
    y: "12",
    width: "2",
    height: "12"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M4,6V8H6V28a2,2,0,0,0,2,2H24a2,2,0,0,0,2-2V8h2V6ZM8,28V8H24V28Z"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "12",
    y: "2",
    width: "8",
    height: "2"
  })),
  "user--avatar": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M16,8a5,5,0,1,0,5,5A5,5,0,0,0,16,8Zm0,8a3,3,0,1,1,3-3A3.0034,3.0034,0,0,1,16,16Z"
  }), "   ", /*#__PURE__*/React.createElement("path", {
    d: "M16,2A14,14,0,1,0,30,16,14.0158,14.0158,0,0,0,16,2ZM10,26.3765V25a3.0033,3.0033,0,0,1,3-3h6a3.0033,3.0033,0,0,1,3,3v1.3765a11.8989,11.8989,0,0,1-12,0Zm13.9925-1.4507A5.0016,5.0016,0,0,0,19,20H13a5.0016,5.0016,0,0,0-4.9925,4.9258,12,12,0,1,1,15.985,0Z"
  })),
  "view": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    d: "M30.94,15.66A16.69,16.69,0,0,0,16,5,16.69,16.69,0,0,0,1.06,15.66a1,1,0,0,0,0,.68A16.69,16.69,0,0,0,16,27,16.69,16.69,0,0,0,30.94,16.34,1,1,0,0,0,30.94,15.66ZM16,25c-5.3,0-10.9-3.93-12.93-9C5.1,10.93,10.7,7,16,7s10.9,3.93,12.93,9C26.9,21.07,21.3,25,16,25Z",
    transform: "translate(0 0)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M16,10a6,6,0,1,0,6,6A6,6,0,0,0,16,10Zm0,10a4,4,0,1,1,4-4A4,4,0,0,1,16,20Z",
    transform: "translate(0 0)"
  })),
  "warning--filled": /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("path", {
    id: "Compound_Path",
    d: "M16,2C8.3,2,2,8.3,2,16s6.3,14,14,14s14-6.3,14-14C30,8.3,23.7,2,16,2z M14.9,8h2.2v11h-2.2V8z M16,25 c-0.8,0-1.5-0.7-1.5-1.5S15.2,22,16,22c0.8,0,1.5,0.7,1.5,1.5S16.8,25,16,25z"
  }), " ", /*#__PURE__*/React.createElement("path", {
    id: "inner-path",
    d: "M17.5,23.5c0,0.8-0.7,1.5-1.5,1.5c-0.8,0-1.5-0.7-1.5-1.5S15.2,22,16,22 C16.8,22,17.5,22.7,17.5,23.5z M17.1,8h-2.2v11h2.2V8z",
    fill: "none"
  }))
};
function Icon({
  name,
  size = 16,
  color = 'currentColor',
  style,
  className,
  ...rest
}) {
  const glyph = ICONS[name];
  if (!glyph) {
    console.warn('Icon: unknown name "' + name + '". Available: ' + Object.keys(ICONS).join(', '));
    return null;
  }
  return /*#__PURE__*/React.createElement("svg", _extends({
    xmlns: "http://www.w3.org/2000/svg",
    viewBox: "0 0 32 32",
    width: size,
    height: size,
    fill: color,
    "aria-hidden": "true",
    focusable: "false",
    style: style,
    className: className
  }, rest), glyph);
}
const ICON_NAMES = Object.keys(ICONS);
Object.assign(__ds_scope, { Icon, ICON_NAMES });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/icons/Icon.jsx", error: String((e && e.message) || e) }); }

// components/actions/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const BTN_CSS = `
.p360--btn { position: relative; display: inline-flex; align-items: center; flex-shrink: 0; box-sizing: border-box; margin: 0; cursor: pointer; font-family: var(--font-sans); font-size: var(--body-compact-01-size); line-height: var(--body-compact-01-lh); letter-spacing: 0.16px; font-weight: var(--font-weight-regular); text-align: left; text-decoration: none; vertical-align: top; border: 1px solid transparent; border-radius: 0; outline: none; max-inline-size: 20rem; transition: background-color var(--duration-fast-01) var(--easing-standard-productive), border-color var(--duration-fast-01) var(--easing-standard-productive), color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--btn:focus { border-color: var(--focus); box-shadow: inset 0 0 0 1px var(--focus), inset 0 0 0 2px var(--background); }
.p360--btn--lg { block-size: 3rem; padding-inline: 15px 63px; }
.p360--btn--md { block-size: 2.5rem; padding-inline: 15px 63px; }
.p360--btn--sm { block-size: 2rem; padding-inline: 15px 63px; }
.p360--btn--xs { block-size: 1.5rem; padding-inline: 11px 31px; }
.p360--btn--icon-end .p360--btn__icon { position: absolute; inset-inline-end: 1rem; inset-block-start: 50%; transform: translateY(-50%); }
.p360--btn--primary { background: var(--button-primary); color: var(--text-on-color); }
.p360--btn--primary:hover { background: var(--button-primary-hover); }
.p360--btn--primary:active { background: var(--button-primary-active); }
.p360--btn--secondary { background: var(--button-secondary); color: var(--text-on-color); }
.p360--btn--secondary:hover { background: var(--button-secondary-hover); }
.p360--btn--secondary:active { background: var(--button-secondary-active); }
.p360--btn--tertiary { background: transparent; border-color: var(--button-tertiary); color: var(--button-tertiary); }
.p360--btn--tertiary:hover { background: var(--button-tertiary-hover); border-color: var(--button-tertiary-hover); color: var(--text-inverse); }
.p360--btn--tertiary:active { background: var(--button-tertiary-active); border-color: transparent; color: var(--text-inverse); }
.p360--btn--ghost { background: transparent; color: var(--link-primary); padding-inline-end: 15px; }
.p360--btn--ghost:hover { background: var(--background-hover); color: var(--link-primary-hover); }
.p360--btn--ghost:active { background: var(--background-active); }
.p360--btn--ghost .p360--btn__icon { position: static; transform: none; margin-inline-start: var(--spacing-03); }
.p360--btn--danger { background: var(--button-danger-primary); color: var(--text-on-color); }
.p360--btn--danger:hover { background: var(--button-danger-hover); }
.p360--btn--danger:active { background: var(--button-danger-active); }
.p360--btn--danger--tertiary { background: transparent; border-color: var(--button-danger-secondary); color: var(--button-danger-secondary); }
.p360--btn--danger--tertiary:hover { background: var(--button-danger-hover); border-color: var(--button-danger-hover); color: var(--text-on-color); }
.p360--btn--danger--ghost { background: transparent; color: var(--button-danger-secondary); padding-inline-end: 15px; }
.p360--btn--danger--ghost:hover { background: var(--button-danger-hover); color: var(--text-on-color); }
.p360--btn[disabled], .p360--btn[disabled]:hover { cursor: not-allowed; background: var(--button-disabled); border-color: var(--button-disabled); color: var(--gray-50); }
.p360--btn--tertiary[disabled], .p360--btn--ghost[disabled], .p360--btn--tertiary[disabled]:hover, .p360--btn--ghost[disabled]:hover, .p360--btn--danger--ghost[disabled], .p360--btn--danger--tertiary[disabled] { background: transparent; border-color: transparent; color: var(--text-disabled); }
.p360--btn--tertiary[disabled] { border-color: var(--button-disabled); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Button({
  kind = 'primary',
  size = 'lg',
  renderIcon,
  disabled,
  children,
  className = '',
  ...rest
}) {
  ensureCss('p360-btn-css', BTN_CSS);
  const cls = ['p360--btn', 'p360--btn--' + size, 'p360--btn--' + kind, renderIcon ? 'p360--btn--icon-end' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    className: cls,
    disabled: disabled
  }, rest), children, renderIcon ? /*#__PURE__*/React.createElement("span", {
    className: "p360--btn__icon",
    style: {
      display: 'inline-flex'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: renderIcon,
    size: 16
  })) : null);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/actions/Button.jsx", error: String((e && e.message) || e) }); }

// components/actions/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const ICONBTN_CSS = `
.p360--icon-btn { display: inline-flex; align-items: center; justify-content: center; box-sizing: border-box; border: 1px solid transparent; border-radius: 0; cursor: pointer; padding: 0; outline: none; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--icon-btn--lg { block-size: 3rem; inline-size: 3rem; }
.p360--icon-btn--md { block-size: 2.5rem; inline-size: 2.5rem; }
.p360--icon-btn--sm { block-size: 2rem; inline-size: 2rem; }
.p360--icon-btn--ghost { background: transparent; color: var(--icon-primary); }
.p360--icon-btn--ghost:hover { background: var(--background-hover); }
.p360--icon-btn--ghost:active { background: var(--background-active); }
.p360--icon-btn--primary { background: var(--button-primary); color: var(--icon-on-color); }
.p360--icon-btn--primary:hover { background: var(--button-primary-hover); }
.p360--icon-btn--tertiary { background: transparent; border-color: var(--button-tertiary); color: var(--button-tertiary); }
.p360--icon-btn--tertiary:hover { background: var(--button-tertiary-hover); color: var(--icon-on-color); }
.p360--icon-btn:focus { border-color: var(--focus); box-shadow: inset 0 0 0 1px var(--focus), inset 0 0 0 2px var(--background); }
.p360--icon-btn[disabled] { cursor: not-allowed; color: var(--icon-disabled); background: transparent; border-color: transparent; }
.p360--icon-btn--primary[disabled] { background: var(--button-disabled); color: var(--gray-50); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function IconButton({
  icon = 'edit',
  kind = 'ghost',
  size = 'md',
  label,
  disabled,
  className = '',
  ...rest
}) {
  ensureCss('p360-iconbtn-css', ICONBTN_CSS);
  const cls = ['p360--icon-btn', 'p360--icon-btn--' + size, 'p360--icon-btn--' + kind, className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    className: cls,
    "aria-label": label || icon,
    title: label || undefined,
    disabled: disabled
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 16
  }));
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/actions/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/data/Pagination.jsx
try { (() => {
const {
  useState
} = React;
const PG_CSS = `
.p360--pagination { display: flex; align-items: center; justify-content: space-between; inline-size: 100%; min-block-size: 3rem; background: var(--layer-01); border-block-start: 1px solid var(--border-subtle-01); font-size: var(--body-compact-01-size); letter-spacing: 0.16px; color: var(--text-secondary); }
.p360--pagination__left, .p360--pagination__right { display: flex; align-items: center; block-size: 3rem; }
.p360--pagination__left { padding-inline-start: var(--spacing-05); gap: var(--spacing-03); }
.p360--pagination__select { appearance: none; -webkit-appearance: none; border: 0; background: transparent; color: var(--text-primary); font-family: inherit; font-size: var(--body-compact-01-size); block-size: 3rem; padding: 0 2rem 0 var(--spacing-03); cursor: pointer; outline: none; }
.p360--pagination__select-wrap { position: relative; display: inline-flex; align-items: center; block-size: 3rem; border-inline-start: 1px solid var(--border-subtle-01); border-inline-end: 1px solid var(--border-subtle-01); }
.p360--pagination__select-wrap:hover { background: var(--layer-hover-01); }
.p360--pagination__select-arrow { position: absolute; inset-inline-end: var(--spacing-03); pointer-events: none; display: inline-flex; color: var(--icon-primary); }
.p360--pagination__btn { display: inline-flex; align-items: center; justify-content: center; inline-size: 3rem; block-size: 3rem; border: 0; border-inline-start: 1px solid var(--border-subtle-01); background: transparent; color: var(--icon-primary); cursor: pointer; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--pagination__btn:hover { background: var(--layer-hover-01); }
.p360--pagination__btn[disabled] { color: var(--icon-disabled); cursor: not-allowed; background: transparent; }
.p360--pagination__text { padding-inline: var(--spacing-05); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Pagination({
  totalItems = 0,
  pageSizes = [10, 20, 30, 50],
  defaultPageSize,
  onChange,
  className = ''
}) {
  ensureCss('p360-pg-css', PG_CSS);
  const [pageSize, setPageSize] = useState(defaultPageSize || pageSizes[0]);
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const set = (p, s) => {
    setPage(p);
    setPageSize(s);
    onChange && onChange({
      page: p,
      pageSize: s
    });
  };
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--pagination ' + className).trim()
  }, /*#__PURE__*/React.createElement("div", {
    className: "p360--pagination__left"
  }, /*#__PURE__*/React.createElement("span", null, "Items per page:"), /*#__PURE__*/React.createElement("span", {
    className: "p360--pagination__select-wrap"
  }, /*#__PURE__*/React.createElement("select", {
    className: "p360--pagination__select",
    value: pageSize,
    onChange: e => set(1, Number(e.target.value)),
    "aria-label": "Items per page"
  }, pageSizes.map(s => /*#__PURE__*/React.createElement("option", {
    key: s,
    value: s
  }, s))), /*#__PURE__*/React.createElement("span", {
    className: "p360--pagination__select-arrow"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron--down",
    size: 16
  }))), /*#__PURE__*/React.createElement("span", {
    className: "p360--pagination__text"
  }, start, "\u2013", end, " of ", totalItems, " items")), /*#__PURE__*/React.createElement("div", {
    className: "p360--pagination__right"
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--pagination__select-wrap",
    style: {
      borderInlineEnd: 0
    }
  }, /*#__PURE__*/React.createElement("select", {
    className: "p360--pagination__select",
    value: page,
    onChange: e => set(Number(e.target.value), pageSize),
    "aria-label": "Page number"
  }, Array.from({
    length: totalPages
  }, (_, i) => /*#__PURE__*/React.createElement("option", {
    key: i,
    value: i + 1
  }, i + 1))), /*#__PURE__*/React.createElement("span", {
    className: "p360--pagination__select-arrow"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron--down",
    size: 16
  }))), /*#__PURE__*/React.createElement("span", {
    className: "p360--pagination__text"
  }, "of ", totalPages, " pages"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--pagination__btn",
    "aria-label": "Previous page",
    disabled: page <= 1,
    onClick: () => set(page - 1, pageSize)
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron--left",
    size: 16
  })), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--pagination__btn",
    "aria-label": "Next page",
    disabled: page >= totalPages,
    onClick: () => set(page + 1, pageSize)
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron--right",
    size: 16
  }))));
}
Object.assign(__ds_scope, { Pagination });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Pagination.jsx", error: String((e && e.message) || e) }); }

// components/data/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Exact tag component-token colors (white theme) from carbon packages/themes/src/component-tokens/tag */
const TAG_COLORS = {
  gray: {
    bg: '#e0e0e0',
    fg: '#161616',
    hover: '#d1d1d1',
    border: '#a8a8a8'
  },
  'cool-gray': {
    bg: '#dde1e6',
    fg: '#121619',
    hover: '#cdd3da',
    border: '#a2a9b0'
  },
  'warm-gray': {
    bg: '#e5e0df',
    fg: '#171414',
    hover: '#d8d0cf',
    border: '#ada8a8'
  },
  red: {
    bg: '#ffd7d9',
    fg: '#a2191f',
    hover: '#ffc2c5',
    border: '#ff8389'
  },
  magenta: {
    bg: '#ffd6e8',
    fg: '#9f1853',
    hover: '#ffbdda',
    border: '#ff7eb6'
  },
  purple: {
    bg: '#e8daff',
    fg: '#6929c4',
    hover: '#dcc7ff',
    border: '#be95ff'
  },
  blue: {
    bg: '#d0e2ff',
    fg: '#0043ce',
    hover: '#b8d3ff',
    border: '#78a9ff'
  },
  cyan: {
    bg: '#bae6ff',
    fg: '#00539a',
    hover: '#99daff',
    border: '#33b1ff'
  },
  teal: {
    bg: '#9ef0f0',
    fg: '#005d5d',
    hover: '#57e5e5',
    border: '#08bdba'
  },
  green: {
    bg: '#a7f0ba',
    fg: '#0e6027',
    hover: '#74e792',
    border: '#42be65'
  },
  'high-contrast': {
    bg: '#393939',
    fg: '#ffffff',
    hover: '#474747',
    border: '#393939'
  }
};
const TAG_CSS = `
.p360--tag { display: inline-flex; align-items: center; justify-content: center; gap: 0; border: 0; border-radius: 1rem; cursor: default; max-inline-size: 13rem; min-inline-size: 2rem; padding-inline: var(--spacing-03); vertical-align: middle; font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; font-weight: var(--font-weight-regular); }
.p360--tag--md { min-block-size: 1.5rem; }
.p360--tag--sm { min-block-size: 1.125rem; }
.p360--tag--lg { min-block-size: 2rem; padding-inline: var(--spacing-04); font-size: var(--label-02-size); }
.p360--tag__label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p360--tag--outline { background: var(--background) !important; color: var(--text-primary) !important; outline: 1px solid var(--border-inverse); outline-offset: -1px; }
.p360--tag__close { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; padding: 0; border: 0; border-radius: 50%; margin-inline-start: 2px; margin-inline-end: -6px; inline-size: 1.5rem; block-size: 1.5rem; background: transparent; color: currentColor; cursor: pointer; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--tag__close:hover { background: rgba(0,0,0,0.12); }
.p360--tag__icon { display: inline-flex; margin-inline-end: var(--spacing-02); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Tag({
  type = 'gray',
  size = 'md',
  filter,
  outline,
  renderIcon,
  onClose,
  children,
  className = '',
  ...rest
}) {
  ensureCss('p360-tag-css', TAG_CSS);
  const c = TAG_COLORS[type] || TAG_COLORS.gray;
  const cls = ['p360--tag', 'p360--tag--' + size, outline ? 'p360--tag--outline' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    style: {
      background: c.bg,
      color: c.fg
    }
  }, rest), renderIcon ? /*#__PURE__*/React.createElement("span", {
    className: "p360--tag__icon"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: renderIcon,
    size: 12
  })) : null, /*#__PURE__*/React.createElement("span", {
    className: "p360--tag__label"
  }, children), filter ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--tag__close",
    "aria-label": "Remove",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "close",
    size: 16
  })) : null);
}
const TAG_TYPES = Object.keys(TAG_COLORS);
Object.assign(__ds_scope, { Tag, TAG_TYPES });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Tag.jsx", error: String((e && e.message) || e) }); }

// components/feedback/InlineNotification.jsx
try { (() => {
const KINDS = {
  error: {
    icon: 'error--filled',
    color: 'var(--support-error)',
    bg: 'var(--notification-background-error)',
    border: 'var(--support-error)'
  },
  success: {
    icon: 'checkmark--filled',
    color: 'var(--support-success)',
    bg: 'var(--notification-background-success)',
    border: 'var(--support-success)'
  },
  warning: {
    icon: 'warning--filled',
    color: 'var(--support-warning)',
    bg: 'var(--notification-background-warning)',
    border: 'var(--support-warning)'
  },
  info: {
    icon: 'information--filled',
    color: 'var(--support-info)',
    bg: 'var(--notification-background-info)',
    border: 'var(--support-info)'
  }
};
const IN_CSS = `
.p360--inline-notification { display: flex; align-items: flex-start; inline-size: 100%; max-inline-size: 42rem; min-block-size: 3rem; box-sizing: border-box; border-inline-start: 3px solid; }
.p360--inline-notification__icon { display: inline-flex; flex-shrink: 0; margin: var(--spacing-05) 0 var(--spacing-05) var(--spacing-05); }
.p360--inline-notification__body { flex: 1; display: flex; flex-wrap: wrap; column-gap: var(--spacing-02); padding: 0.9375rem var(--spacing-03) 0.9375rem var(--spacing-05); font-size: var(--body-compact-01-size); line-height: var(--body-compact-01-lh); letter-spacing: 0.16px; color: var(--text-primary); }
.p360--inline-notification__title { font-weight: var(--font-weight-semibold); }
.p360--inline-notification__close { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; inline-size: 3rem; block-size: 3rem; border: 0; background: transparent; color: var(--icon-primary); cursor: pointer; }
.p360--inline-notification__close:hover { background: rgba(0,0,0,0.08); }
.p360--inline-notification--hct { background: var(--background-inverse) !important; color: var(--text-inverse); border-inline-start-color: currentColor; }
.p360--inline-notification--hct .p360--inline-notification__body { color: var(--text-inverse); }
.p360--inline-notification--hct .p360--inline-notification__close { color: var(--icon-inverse); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function InlineNotification({
  kind = 'info',
  title,
  subtitle,
  hideCloseButton,
  highContrast,
  onClose,
  className = ''
}) {
  ensureCss('p360-in-css', IN_CSS);
  const k = KINDS[kind] || KINDS.info;
  return /*#__PURE__*/React.createElement("div", {
    className: ['p360--inline-notification', highContrast ? 'p360--inline-notification--hct' : '', className].filter(Boolean).join(' '),
    style: {
      background: highContrast ? undefined : k.bg,
      borderInlineStartColor: k.border
    },
    role: "status"
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--inline-notification__icon"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: k.icon,
    size: 20,
    color: k.color
  })), /*#__PURE__*/React.createElement("div", {
    className: "p360--inline-notification__body"
  }, title ? /*#__PURE__*/React.createElement("span", {
    className: "p360--inline-notification__title"
  }, title) : null, subtitle ? /*#__PURE__*/React.createElement("span", null, subtitle) : null), !hideCloseButton ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--inline-notification__close",
    "aria-label": "Close notification",
    onClick: onClose
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "close",
    size: 16
  })) : null);
}
Object.assign(__ds_scope, { InlineNotification });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/InlineNotification.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Modal.jsx
try { (() => {
const MD_CSS = `
.p360--modal { position: fixed; inset: 0; z-index: 9000; display: flex; align-items: center; justify-content: center; background: var(--overlay); opacity: 1; transition: opacity var(--duration-moderate-02) var(--easing-entrance-expressive); }
.p360--modal__container { position: relative; display: flex; flex-direction: column; inline-size: 100%; max-inline-size: 40rem; max-block-size: 90vh; background: var(--layer-01); overflow: hidden; }
.p360--modal__container--sm { max-inline-size: 24rem; }
.p360--modal__container--lg { max-inline-size: 60rem; }
.p360--modal__header { padding: var(--spacing-05) var(--spacing-09) var(--spacing-03) var(--spacing-05); }
.p360--modal__label { margin: 0 0 var(--spacing-02); color: var(--text-secondary); font-size: var(--label-01-size); letter-spacing: 0.32px; }
.p360--modal__heading { margin: 0; color: var(--text-primary); font-size: var(--heading-03-size); line-height: var(--heading-03-lh); font-weight: var(--font-weight-regular); }
.p360--modal__close { position: absolute; inset-block-start: 0; inset-inline-end: 0; display: inline-flex; align-items: center; justify-content: center; inline-size: 3rem; block-size: 3rem; border: 0; background: transparent; color: var(--icon-primary); cursor: pointer; }
.p360--modal__close:hover { background: var(--layer-hover-01); }
.p360--modal__content { flex: 1; padding: var(--spacing-03) 20% var(--spacing-09) var(--spacing-05); overflow-y: auto; color: var(--text-primary); font-size: var(--body-01-size); line-height: var(--body-01-lh); letter-spacing: 0.16px; }
.p360--modal__footer { display: flex; justify-content: flex-end; }
.p360--modal__footer .p360--btn { flex: 0 1 50%; max-inline-size: none; block-size: 4rem; margin: 0; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Modal({
  open,
  label,
  heading,
  children,
  size = 'md',
  primaryButtonText = 'Confirm',
  secondaryButtonText = 'Cancel',
  danger,
  onRequestClose,
  onRequestSubmit,
  className = ''
}) {
  ensureCss('p360-md-css', MD_CSS);
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--modal ' + className).trim(),
    onClick: e => {
      if (e.target === e.currentTarget && onRequestClose) onRequestClose();
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: ['p360--modal__container', size !== 'md' ? 'p360--modal__container--' + size : ''].filter(Boolean).join(' '),
    role: "dialog",
    "aria-modal": "true"
  }, /*#__PURE__*/React.createElement("div", {
    className: "p360--modal__header"
  }, label ? /*#__PURE__*/React.createElement("p", {
    className: "p360--modal__label"
  }, label) : null, /*#__PURE__*/React.createElement("h3", {
    className: "p360--modal__heading"
  }, heading)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--modal__close",
    "aria-label": "Close",
    onClick: onRequestClose
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "close",
    size: 20
  })), /*#__PURE__*/React.createElement("div", {
    className: "p360--modal__content"
  }, children), /*#__PURE__*/React.createElement("div", {
    className: "p360--modal__footer"
  }, /*#__PURE__*/React.createElement(__ds_scope.Button, {
    kind: "secondary",
    onClick: onRequestClose
  }, secondaryButtonText), /*#__PURE__*/React.createElement(__ds_scope.Button, {
    kind: danger ? 'danger' : 'primary',
    onClick: onRequestSubmit
  }, primaryButtonText))));
}
Object.assign(__ds_scope, { Modal });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Modal.jsx", error: String((e && e.message) || e) }); }

// components/forms/Search.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const {
  useState
} = React;
const SR_CSS = `
.p360--search { position: relative; display: flex; align-items: center; inline-size: 100%; }
.p360--search__input { box-sizing: border-box; inline-size: 100%; border: none; border-block-end: 1px solid var(--border-strong-01); border-radius: 0; background: var(--field-01); color: var(--text-primary); font-family: inherit; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; padding: 0 var(--spacing-08) 0 var(--spacing-08); outline: none; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--search--lg .p360--search__input { block-size: 3rem; }
.p360--search--md .p360--search__input { block-size: 2.5rem; }
.p360--search--sm .p360--search__input { block-size: 2rem; padding-inline-start: 2rem; }
.p360--search__input:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--search__input::placeholder { color: var(--text-placeholder); opacity: 1; }
.p360--search__magnifier { position: absolute; inset-inline-start: var(--spacing-05); color: var(--icon-secondary); display: inline-flex; pointer-events: none; }
.p360--search--sm .p360--search__magnifier { inset-inline-start: var(--spacing-03); }
.p360--search__close { position: absolute; inset-inline-end: 0; display: inline-flex; align-items: center; justify-content: center; inline-size: 2.5rem; block-size: 100%; border: 0; background: transparent; color: var(--icon-primary); cursor: pointer; }
.p360--search__close:hover { background: var(--field-hover-01); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Search({
  placeholder = 'Search',
  size = 'md',
  value,
  defaultValue,
  onChange,
  className = '',
  id,
  ...rest
}) {
  ensureCss('p360-sr-css', SR_CSS);
  const [internal, setInternal] = useState(defaultValue || '');
  const val = value !== undefined ? value : internal;
  const handle = e => {
    if (value === undefined) setInternal(e.target.value);
    onChange && onChange(e);
  };
  const clear = () => {
    const e = {
      target: {
        value: ''
      }
    };
    if (value === undefined) setInternal('');
    onChange && onChange(e);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: ['p360--search', 'p360--search--' + size, className].filter(Boolean).join(' '),
    role: "search"
  }, /*#__PURE__*/React.createElement("span", {
    className: "p360--search__magnifier"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "search",
    size: 16
  })), /*#__PURE__*/React.createElement("input", _extends({
    id: id,
    type: "text",
    className: "p360--search__input",
    placeholder: placeholder,
    value: val,
    onChange: handle
  }, rest)), val ? /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--search__close",
    "aria-label": "Clear search",
    onClick: clear
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "close",
    size: 16
  })) : null);
}
Object.assign(__ds_scope, { Search });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Search.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SEL_CSS = `
.p360--form-item { display: flex; flex-direction: column; align-items: flex-start; inline-size: 100%; }
.p360--label { display: inline-block; margin-block-end: var(--spacing-03); color: var(--text-secondary); font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; font-weight: var(--font-weight-regular); }
.p360--label--disabled { color: var(--text-disabled); }
.p360--form__helper-text { margin-block-start: var(--spacing-02); color: var(--text-helper); font-size: var(--helper-text-01-size); line-height: var(--helper-text-01-lh); letter-spacing: 0.32px; }
.p360--form-requirement { margin-block-start: var(--spacing-02); color: var(--text-error); font-size: var(--helper-text-01-size); line-height: var(--helper-text-01-lh); letter-spacing: 0.32px; }

.p360--select__wrapper { position: relative; display: flex; inline-size: 100%; }
.p360--select { box-sizing: border-box; inline-size: 100%; appearance: none; -webkit-appearance: none; border: none; border-block-end: 1px solid var(--border-strong-01); border-radius: 0; background: var(--field-01); color: var(--text-primary); font-family: inherit; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; padding: 0 var(--spacing-09) 0 var(--spacing-05); outline: none; cursor: pointer; }
.p360--select--lg { block-size: 3rem; }
.p360--select--md { block-size: 2.5rem; }
.p360--select--sm { block-size: 2rem; }
.p360--select:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--select[disabled] { border-block-end-color: transparent; color: var(--text-disabled); cursor: not-allowed; }
.p360--select__arrow { position: absolute; inset-block-start: 50%; inset-inline-end: var(--spacing-05); transform: translateY(-50%); pointer-events: none; color: var(--icon-primary); display: inline-flex; }
.p360--select--invalid { outline: 2px solid var(--support-error); outline-offset: -2px; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Select({
  labelText,
  helperText,
  invalid,
  invalidText,
  size = 'md',
  disabled,
  items = [],
  className = '',
  id,
  ...rest
}) {
  ensureCss('p360-sel-css', SEL_CSS);
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--form-item ' + className).trim()
  }, labelText ? /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    className: 'p360--label' + (disabled ? ' p360--label--disabled' : '')
  }, labelText) : null, /*#__PURE__*/React.createElement("div", {
    className: "p360--select__wrapper"
  }, /*#__PURE__*/React.createElement("select", _extends({
    id: id,
    className: ['p360--select', 'p360--select--' + size, invalid ? 'p360--select--invalid' : ''].filter(Boolean).join(' '),
    disabled: disabled
  }, rest), items.map((it, i) => typeof it === 'string' ? /*#__PURE__*/React.createElement("option", {
    key: i,
    value: it
  }, it) : /*#__PURE__*/React.createElement("option", {
    key: i,
    value: it.value
  }, it.label))), /*#__PURE__*/React.createElement("span", {
    className: "p360--select__arrow"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron--down",
    size: 16
  }))), invalid && invalidText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--form-requirement"
  }, invalidText) : helperText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--form__helper-text"
  }, helperText) : null);
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/TextInput.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TI_CSS = `
.p360--form-item { display: flex; flex-direction: column; align-items: flex-start; inline-size: 100%; }
.p360--label { display: inline-block; margin-block-end: var(--spacing-03); color: var(--text-secondary); font-size: var(--label-01-size); line-height: var(--label-01-lh); letter-spacing: 0.32px; font-weight: var(--font-weight-regular); }
.p360--label--disabled { color: var(--text-disabled); }
.p360--form__helper-text { margin-block-start: var(--spacing-02); color: var(--text-helper); font-size: var(--helper-text-01-size); line-height: var(--helper-text-01-lh); letter-spacing: 0.32px; }
.p360--form-requirement { margin-block-start: var(--spacing-02); color: var(--text-error); font-size: var(--helper-text-01-size); line-height: var(--helper-text-01-lh); letter-spacing: 0.32px; }

.p360--text-input__wrapper { position: relative; display: flex; inline-size: 100%; }
.p360--text-input { box-sizing: border-box; inline-size: 100%; border: none; border-block-end: 1px solid var(--border-strong-01); border-radius: 0; background: var(--field-01); color: var(--text-primary); font-family: inherit; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; padding: 0 var(--spacing-05); outline: none; transition: background-color var(--duration-fast-01) var(--easing-standard-productive), outline var(--duration-fast-01) var(--easing-standard-productive); }
.p360--text-input--lg { block-size: 3rem; }
.p360--text-input--md { block-size: 2.5rem; }
.p360--text-input--sm { block-size: 2rem; }
.p360--text-input::placeholder { color: var(--text-placeholder); opacity: 1; }
.p360--text-input:focus, .p360--text-input:active { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--text-input--invalid { outline: 2px solid var(--support-error); outline-offset: -2px; padding-inline-end: var(--spacing-08); }
.p360--text-input[disabled] { border-block-end-color: transparent; color: var(--text-disabled); -webkit-text-fill-color: var(--text-disabled); cursor: not-allowed; }
.p360--text-input__invalid-icon { position: absolute; inset-block-start: 50%; inset-inline-end: var(--spacing-05); transform: translateY(-50%); color: var(--support-error); pointer-events: none; display: inline-flex; }
.p360--text-input--light { background: var(--field-02); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function TextInput({
  labelText,
  helperText,
  invalid,
  invalidText,
  size = 'md',
  light,
  disabled,
  placeholder,
  className = '',
  id,
  ...rest
}) {
  ensureCss('p360-ti-css', TI_CSS);
  const inputCls = ['p360--text-input', 'p360--text-input--' + size, invalid ? 'p360--text-input--invalid' : '', light ? 'p360--text-input--light' : ''].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--form-item ' + className).trim()
  }, labelText ? /*#__PURE__*/React.createElement("label", {
    htmlFor: id,
    className: 'p360--label' + (disabled ? ' p360--label--disabled' : '')
  }, labelText) : null, /*#__PURE__*/React.createElement("div", {
    className: "p360--text-input__wrapper"
  }, /*#__PURE__*/React.createElement("input", _extends({
    id: id,
    type: "text",
    className: inputCls,
    placeholder: placeholder,
    disabled: disabled
  }, rest)), invalid ? /*#__PURE__*/React.createElement("span", {
    className: "p360--text-input__invalid-icon"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "warning--filled",
    size: 16,
    color: "var(--support-error)"
  })) : null), invalid && invalidText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--form-requirement"
  }, invalidText) : helperText ? /*#__PURE__*/React.createElement("div", {
    className: "p360--form__helper-text"
  }, helperText) : null);
}
Object.assign(__ds_scope, { TextInput });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/TextInput.jsx", error: String((e && e.message) || e) }); }

// components/layout/Accordion.jsx
try { (() => {
const {
  useState
} = React;
const ACC_CSS = `
.p360--accordion { list-style: none; margin: 0; padding: 0; inline-size: 100%; }
.p360--accordion__item { border-block-start: 1px solid var(--border-subtle-00); overflow: visible; }
.p360--accordion__item:last-child { border-block-end: 1px solid var(--border-subtle-00); }
.p360--accordion__heading { display: flex; align-items: center; justify-content: space-between; inline-size: 100%; min-block-size: 2.5rem; margin: 0; padding: var(--spacing-03) 0 var(--spacing-03) var(--spacing-05); background: transparent; border: 0; cursor: pointer; color: var(--text-primary); font-family: inherit; font-size: var(--body-01-size); line-height: var(--body-01-lh); text-align: left; transition: background-color var(--duration-fast-02) var(--easing-standard-productive); }
.p360--accordion__heading:hover { background: var(--layer-hover-01); }
.p360--accordion__heading:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--accordion__arrow { flex-shrink: 0; margin-inline-end: var(--spacing-05); transition: transform var(--duration-fast-02) var(--easing-standard-productive); }
.p360--accordion__item--open .p360--accordion__arrow { transform: rotate(180deg); }
.p360--accordion__content { padding: var(--spacing-03) var(--spacing-05) var(--spacing-06); padding-inline-end: 25%; font-size: var(--body-01-size); line-height: var(--body-01-lh); color: var(--text-primary); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Accordion({
  items = [],
  defaultOpen = -1,
  className = ''
}) {
  ensureCss('p360-accordion-css', ACC_CSS);
  const [open, setOpen] = useState(defaultOpen);
  return /*#__PURE__*/React.createElement("ul", {
    className: ('p360--accordion ' + className).trim()
  }, items.map((it, i) => /*#__PURE__*/React.createElement("li", {
    key: i,
    className: 'p360--accordion__item' + (open === i ? ' p360--accordion__item--open' : '')
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--accordion__heading",
    "aria-expanded": open === i,
    onClick: () => setOpen(open === i ? -1 : i)
  }, /*#__PURE__*/React.createElement("span", null, it.title), /*#__PURE__*/React.createElement("span", {
    className: "p360--accordion__arrow"
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron--down",
    size: 16
  }))), open === i ? /*#__PURE__*/React.createElement("div", {
    className: "p360--accordion__content"
  }, it.content) : null)));
}
Object.assign(__ds_scope, { Accordion });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Accordion.jsx", error: String((e && e.message) || e) }); }

// components/layout/Link.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const LINK_CSS = `
.p360--link { display: inline-flex; align-items: center; gap: var(--spacing-03); color: var(--link-primary); text-decoration: none; cursor: pointer; outline: none; font-size: var(--body-compact-01-size); line-height: var(--body-compact-01-lh); letter-spacing: 0.16px; }
.p360--link:hover { color: var(--link-primary-hover); text-decoration: underline; }
.p360--link:focus { outline: 1px solid var(--focus); }
.p360--link--inline { text-decoration: underline; }
.p360--link--disabled, .p360--link--disabled:hover { color: var(--text-disabled); cursor: not-allowed; text-decoration: none; }
.p360--link--lg { font-size: var(--body-compact-02-size); }
.p360--link--sm { font-size: var(--helper-text-01-size); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Link({
  href = '#',
  size = 'md',
  inline,
  disabled,
  renderIcon,
  children,
  className = '',
  ...rest
}) {
  ensureCss('p360-link-css', LINK_CSS);
  const cls = ['p360--link', size !== 'md' ? 'p360--link--' + size : '', inline ? 'p360--link--inline' : '', disabled ? 'p360--link--disabled' : '', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("a", _extends({
    href: disabled ? undefined : href,
    className: cls,
    "aria-disabled": disabled || undefined
  }, rest), children, renderIcon ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: renderIcon,
    size: size === 'lg' ? 20 : 16
  }) : null);
}
Object.assign(__ds_scope, { Link });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Link.jsx", error: String((e && e.message) || e) }); }

// components/layout/OverflowMenu.jsx
try { (() => {
const {
  useState,
  useRef,
  useEffect
} = React;
const OFM_CSS = `
.p360--overflow { position: relative; display: inline-block; }
.p360--overflow__trigger { display: inline-flex; align-items: center; justify-content: center; inline-size: 2.5rem; block-size: 2.5rem; padding: 0; border: 0; background: transparent; color: var(--icon-primary); cursor: pointer; transition: background-color var(--duration-fast-01) var(--easing-standard-productive); }
.p360--overflow__trigger:hover { background: var(--background-hover); }
.p360--overflow__trigger:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--overflow__trigger--open { background: var(--layer-02); box-shadow: 0 2px 6px var(--shadow); }
.p360--overflow__menu { position: absolute; z-index: 1000; inset-inline-start: 0; inline-size: 10rem; padding: 0; margin: 0; list-style: none; background: var(--layer-02); box-shadow: 0 2px 6px var(--shadow); }
.p360--overflow__option { display: block; inline-size: 100%; block-size: 2.5rem; padding: 0 var(--spacing-05); border: 0; background: transparent; color: var(--text-secondary); font-family: inherit; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; text-align: left; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p360--overflow__option:hover { background: var(--layer-hover-02); color: var(--text-primary); }
.p360--overflow__option--danger { color: var(--button-danger-secondary); }
.p360--overflow__option--danger:hover { background: var(--button-danger-primary); color: var(--text-on-color); }
.p360--overflow__option--divider { border-block-start: 1px solid var(--border-subtle-00); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function OverflowMenu({
  items = [],
  direction = 'bottom',
  className = ''
}) {
  ensureCss('p360-ofm-css', OFM_CSS);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = e => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);
  const menuPos = direction === 'top' ? {
    insetBlockEnd: '100%'
  } : {
    insetBlockStart: '100%'
  };
  return /*#__PURE__*/React.createElement("div", {
    className: ('p360--overflow ' + className).trim(),
    ref: ref
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Options",
    className: 'p360--overflow__trigger' + (open ? ' p360--overflow__trigger--open' : ''),
    onClick: () => setOpen(!open)
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "overflow-menu--vertical",
    size: 16
  })), open ? /*#__PURE__*/React.createElement("ul", {
    className: "p360--overflow__menu",
    style: menuPos
  }, items.map((it, i) => /*#__PURE__*/React.createElement("li", {
    key: i
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: ['p360--overflow__option', it.danger ? 'p360--overflow__option--danger' : '', it.divider ? 'p360--overflow__option--divider' : ''].filter(Boolean).join(' '),
    onClick: () => {
      setOpen(false);
      it.onClick && it.onClick();
    }
  }, it.label)))) : null);
}
Object.assign(__ds_scope, { OverflowMenu });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/OverflowMenu.jsx", error: String((e && e.message) || e) }); }

// components/layout/Tile.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TILE_CSS = `
.p360--tile { display: block; box-sizing: border-box; min-block-size: 4rem; min-inline-size: 8rem; padding: var(--spacing-05); background: var(--layer-01); color: var(--text-primary); border-radius: 0; outline: none; }
.p360--tile--clickable { cursor: pointer; text-decoration: none; transition: background-color var(--duration-moderate-01) var(--easing-standard-productive); border: 1px solid transparent; }
.p360--tile--clickable:hover { background: var(--layer-hover-01); }
.p360--tile--clickable:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--tile--selectable { cursor: pointer; border: 1px solid transparent; }
.p360--tile--selectable:hover { background: var(--layer-hover-01); }
.p360--tile--selected { outline: 1px solid var(--border-inverse); outline-offset: -1px; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Tile({
  clickable,
  selectable,
  selected,
  href,
  children,
  className = '',
  style,
  ...rest
}) {
  ensureCss('p360-tile-css', TILE_CSS);
  const cls = ['p360--tile', clickable ? 'p360--tile--clickable' : '', selectable ? 'p360--tile--selectable' : '', selected ? 'p360--tile--selected' : '', className].filter(Boolean).join(' ');
  if (clickable) {
    return /*#__PURE__*/React.createElement("a", _extends({
      href: href || '#',
      className: cls,
      style: style
    }, rest), children);
  }
  return /*#__PURE__*/React.createElement("div", _extends({
    className: cls,
    tabIndex: selectable ? 0 : undefined,
    style: style
  }, rest), children);
}
Object.assign(__ds_scope, { Tile });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Tile.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Breadcrumb.jsx
try { (() => {
const BC_CSS = `
.p360--breadcrumb { display: flex; flex-wrap: wrap; align-items: center; list-style: none; margin: 0; padding: 0; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; }
.p360--breadcrumb__item { display: flex; align-items: center; }
.p360--breadcrumb__item::after { content: '/'; margin-inline: var(--spacing-03); color: var(--text-primary); }
.p360--breadcrumb__item:last-child::after { content: ''; margin: 0; }
.p360--breadcrumb__link { color: var(--link-primary); text-decoration: none; }
.p360--breadcrumb__link:hover { color: var(--link-primary-hover); text-decoration: underline; }
.p360--breadcrumb__current { color: var(--text-primary); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Breadcrumb({
  items = [],
  className = ''
}) {
  ensureCss('p360-bc-css', BC_CSS);
  return /*#__PURE__*/React.createElement("nav", {
    "aria-label": "Breadcrumb",
    className: className
  }, /*#__PURE__*/React.createElement("ol", {
    className: "p360--breadcrumb"
  }, items.map((it, i) => {
    const isLast = i === items.length - 1;
    const label = typeof it === 'string' ? it : it.label;
    const href = typeof it === 'string' ? '#' : it.href || '#';
    return /*#__PURE__*/React.createElement("li", {
      key: i,
      className: "p360--breadcrumb__item"
    }, isLast ? /*#__PURE__*/React.createElement("span", {
      className: "p360--breadcrumb__current",
      "aria-current": "page"
    }, label) : /*#__PURE__*/React.createElement("a", {
      className: "p360--breadcrumb__link",
      href: href
    }, label));
  })));
}
Object.assign(__ds_scope, { Breadcrumb });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Breadcrumb.jsx", error: String((e && e.message) || e) }); }

// components/navigation/ContentSwitcher.jsx
try { (() => {
const {
  useState
} = React;
const CS_CSS = `
.p360--content-switcher { display: inline-flex; align-items: stretch; block-size: 2.5rem; border-radius: 4px; }
.p360--content-switcher__btn { position: relative; display: inline-flex; align-items: center; justify-content: center; padding: 0 var(--spacing-05); border: 0; background: transparent; color: var(--text-secondary); font-family: inherit; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; cursor: pointer; transition: background-color var(--duration-fast-01) var(--easing-standard-productive), color var(--duration-fast-01) var(--easing-standard-productive); white-space: nowrap; }
.p360--content-switcher__btn:first-child { border-start-start-radius: 4px; border-end-start-radius: 4px; }
.p360--content-switcher__btn:last-child { border-start-end-radius: 4px; border-end-end-radius: 4px; }
.p360--content-switcher__btn:not(:first-child)::before { content: ''; position: absolute; inset-inline-start: 0; inset-block-start: 25%; block-size: 50%; inline-size: 1px; background: var(--border-strong-01); }
.p360--content-switcher__btn:hover { background: var(--layer-hover-01); color: var(--text-primary); }
.p360--content-switcher__btn--selected { background: var(--layer-selected-inverse); color: var(--text-inverse); z-index: 1; }
.p360--content-switcher__btn--selected::before, .p360--content-switcher__btn--selected + .p360--content-switcher__btn::before { display: none; }
.p360--content-switcher__btn--selected:hover { background: var(--layer-selected-inverse); color: var(--text-inverse); }
.p360--content-switcher__btn:focus { outline: 2px solid var(--focus); outline-offset: -2px; z-index: 2; }
.p360--content-switcher--sm { block-size: 2rem; }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function ContentSwitcher({
  options = [],
  defaultSelected = 0,
  size = 'md',
  onChange,
  className = ''
}) {
  ensureCss('p360-cs-css', CS_CSS);
  const [sel, setSel] = useState(defaultSelected);
  return /*#__PURE__*/React.createElement("div", {
    className: ['p360--content-switcher', size === 'sm' ? 'p360--content-switcher--sm' : '', className].filter(Boolean).join(' '),
    role: "tablist"
  }, options.map((o, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    type: "button",
    role: "tab",
    "aria-selected": sel === i,
    className: 'p360--content-switcher__btn' + (sel === i ? ' p360--content-switcher__btn--selected' : ''),
    onClick: () => {
      setSel(i);
      onChange && onChange(i);
    }
  }, o)));
}
Object.assign(__ds_scope, { ContentSwitcher });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/ContentSwitcher.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Header.jsx
try { (() => {
const HD_CSS = `
.p360--header { position: relative; display: flex; align-items: center; inline-size: 100%; block-size: 3rem; background: var(--gray-100); border-block-end: 1px solid var(--gray-80); box-sizing: border-box; z-index: 100; }
.p360--header__menu-trigger { display: inline-flex; align-items: center; justify-content: center; inline-size: 3rem; block-size: 3rem; border: 0; background: transparent; color: var(--white); cursor: pointer; }
.p360--header__menu-trigger:hover { background: var(--gray-90-hover); }
.p360--header__name { display: flex; align-items: center; padding: 0 var(--spacing-07) 0 var(--spacing-05); color: var(--white); font-size: var(--body-compact-01-size); letter-spacing: 0.16px; text-decoration: none; block-size: 100%; user-select: none; }
.p360--header__name-prefix { font-weight: var(--font-weight-regular); margin-inline-end: 0.25rem; }
.p360--header__name-main { font-weight: var(--font-weight-semibold); }
.p360--header__nav { display: flex; align-items: center; block-size: 100%; }
.p360--header__link { position: relative; display: inline-flex; align-items: center; padding: 0 var(--spacing-05); block-size: 100%; color: var(--gray-30); font-size: var(--body-compact-01-size); letter-spacing: 0.16px; text-decoration: none; border-block-end: 3px solid transparent; border-block-start: 3px solid transparent; box-sizing: border-box; }
.p360--header__link:hover { background: var(--gray-90-hover); color: var(--white); }
.p360--header__link--current { color: var(--white); border-block-end-color: var(--blue-60); }
.p360--header__spacer { flex: 1; }
.p360--header__action { display: inline-flex; align-items: center; justify-content: center; inline-size: 3rem; block-size: 3rem; border: 0; background: transparent; color: var(--white); cursor: pointer; }
.p360--header__action:hover { background: var(--gray-90-hover); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Header({
  prefix = 'Plant360',
  name = '.AI',
  logoSrc,
  links = [],
  currentLink,
  actions = ['search', 'notification', 'user--avatar'],
  onMenuClick,
  onActionClick,
  className = ''
}) {
  ensureCss('p360-hd-css', HD_CSS);
  return /*#__PURE__*/React.createElement("header", {
    className: ('p360--header ' + className).trim()
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "p360--header__menu-trigger",
    "aria-label": "Open menu",
    onClick: onMenuClick
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "menu",
    size: 20
  })), /*#__PURE__*/React.createElement("a", {
    href: "#",
    className: "p360--header__name"
  }, logoSrc ? /*#__PURE__*/React.createElement("img", {
    src: logoSrc,
    alt: prefix + name,
    style: {
      height: '14px',
      width: 'auto',
      display: 'block'
    }
  }) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: "p360--header__name-main"
  }, prefix), /*#__PURE__*/React.createElement("span", {
    className: "p360--header__name-prefix"
  }, name))), /*#__PURE__*/React.createElement("nav", {
    className: "p360--header__nav"
  }, links.map((l, i) => /*#__PURE__*/React.createElement("a", {
    key: i,
    href: "#",
    className: 'p360--header__link' + (l === currentLink ? ' p360--header__link--current' : '')
  }, l))), /*#__PURE__*/React.createElement("span", {
    className: "p360--header__spacer"
  }), actions.map((a, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    type: "button",
    className: "p360--header__action",
    "aria-label": a,
    onClick: () => onActionClick && onActionClick(a)
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: a,
    size: 20
  }))));
}
Object.assign(__ds_scope, { Header });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Header.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
const {
  useState
} = React;
const TB_CSS = `
.p360--tabs { display: flex; align-items: flex-end; inline-size: 100%; box-shadow: inset 0 -1px 0 var(--border-subtle-00); }
.p360--tabs__tab { position: relative; display: inline-flex; align-items: center; block-size: 3rem; padding: 0 var(--spacing-05); border: 0; border-block-end: 2px solid transparent; background: transparent; color: var(--text-secondary); font-family: inherit; font-size: var(--body-compact-01-size); letter-spacing: 0.16px; cursor: pointer; transition: color var(--duration-fast-01) var(--easing-standard-productive), border-color var(--duration-fast-01) var(--easing-standard-productive); box-sizing: border-box; }
.p360--tabs__tab:hover { color: var(--text-primary); border-block-end-color: var(--border-strong-01); }
.p360--tabs__tab--selected { color: var(--text-primary); font-weight: var(--font-weight-semibold); border-block-end-color: var(--border-interactive); }
.p360--tabs__tab[disabled] { color: var(--text-disabled); cursor: not-allowed; border-block-end-color: transparent; }
.p360--tabs__tab:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.p360--tabs__panel { padding: var(--spacing-05) 0; font-size: var(--body-01-size); line-height: var(--body-01-lh); }
.p360--tabs--contained { box-shadow: none; }
.p360--tabs--contained .p360--tabs__tab { background: var(--layer-accent-01); block-size: 3rem; border-block-end: 0; border-block-start: 2px solid transparent; margin-inline-end: 1px; }
.p360--tabs--contained .p360--tabs__tab--selected { background: var(--layer-01); border-block-start-color: var(--border-interactive); }
`;
function ensureCss(id, css) {
  if (typeof document !== 'undefined' && !document.getElementById(id)) {
    const s = document.createElement('style');
    s.id = id;
    s.textContent = css;
    document.head.appendChild(s);
  }
}
function Tabs({
  tabs = [],
  defaultSelected = 0,
  contained,
  onChange,
  className = ''
}) {
  ensureCss('p360-tb-css', TB_CSS);
  const [sel, setSel] = useState(defaultSelected);
  const current = tabs[sel];
  return /*#__PURE__*/React.createElement("div", {
    className: className
  }, /*#__PURE__*/React.createElement("div", {
    className: 'p360--tabs' + (contained ? ' p360--tabs--contained' : ''),
    role: "tablist"
  }, tabs.map((t, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    type: "button",
    role: "tab",
    "aria-selected": sel === i,
    disabled: t.disabled,
    className: 'p360--tabs__tab' + (sel === i ? ' p360--tabs__tab--selected' : ''),
    onClick: () => {
      setSel(i);
      onChange && onChange(i);
    }
  }, t.label))), current && current.panel !== undefined ? /*#__PURE__*/React.createElement("div", {
    className: "p360--tabs__panel",
    role: "tabpanel"
  }, current.panel) : null);
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// ui_kits/plant360-console/screens.jsx
try { (() => {
// Plant360.AI console screens — composed from design-system components (window.Plant360AIDesignSystem_796edf)
const {
  Button,
  IconButton,
  TextInput,
  Select,
  Checkbox,
  Toggle,
  Search,
  Tag,
  DataTable,
  Pagination,
  Header,
  Tabs,
  Breadcrumb,
  ContentSwitcher,
  InlineNotification,
  Modal,
  ProgressBar,
  Icon,
  Link,
  Tile,
  OverflowMenu
} = window.Plant360AIDesignSystem_796edf;

/* ---------- Side navigation (Carbon UI-shell side-nav pattern) ---------- */
const sideNavCss = document.createElement('style');
sideNavCss.textContent = `
.pc--sidenav { inline-size: 16rem; flex-shrink: 0; background: var(--white); border-inline-end: 1px solid var(--border-subtle-00); padding-block: var(--spacing-05); box-sizing: border-box; }
.pc--sidenav__item { display: flex; align-items: center; gap: var(--spacing-04); inline-size: 100%; block-size: 2rem; padding: 0 var(--spacing-05); border: 0; background: transparent; color: var(--text-secondary); font-family: inherit; font-size: var(--heading-compact-01-size); font-weight: var(--font-weight-semibold); letter-spacing: 0.16px; cursor: pointer; text-align: left; box-sizing: border-box; }
.pc--sidenav__item:hover { background: var(--layer-hover-01); color: var(--text-primary); }
.pc--sidenav__item--active { background: var(--layer-selected-01); color: var(--text-primary); box-shadow: inset 3px 0 0 var(--border-interactive); }
.pc--shell { display: flex; min-block-size: calc(100vh - 3rem); background: var(--layer-01); }
.pc--main { flex: 1; padding: var(--spacing-07); box-sizing: border-box; min-inline-size: 0; }
`;
document.head.appendChild(sideNavCss);
function SideNav({
  current,
  onNav
}) {
  const items = [['Dashboard', 'dashboard'], ['Fields', 'map'], ['Sensors', 'temperature'], ['Imagery', 'view'], ['Reports', 'analytics'], ['Settings', 'settings']];
  return /*#__PURE__*/React.createElement("nav", {
    className: "pc--sidenav",
    "aria-label": "Side navigation"
  }, items.map(([label, icon]) => /*#__PURE__*/React.createElement("button", {
    key: label,
    type: "button",
    className: 'pc--sidenav__item' + (current === label ? ' pc--sidenav__item--active' : ''),
    onClick: () => onNav(label)
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 16
  }), label)));
}

/* ---------- Login ---------- */
function LoginScreen({
  onLogin
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: '100vh',
      background: 'var(--layer-01)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 400,
      background: 'var(--white)',
      padding: 'var(--spacing-07)',
      boxSizing: 'border-box'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo/plant360-ai-black.png",
    alt: "Plant360.AI",
    style: {
      height: 18,
      width: 'auto',
      display: 'block',
      marginBottom: 8
    }
  }), /*#__PURE__*/React.createElement("h1", {
    className: "type-heading-03",
    style: {
      margin: '0 0 4px'
    }
  }, "Log in"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '0 0 24px',
      fontSize: 14,
      color: 'var(--text-secondary)'
    }
  }, "Don't have an account? ", /*#__PURE__*/React.createElement(Link, {
    inline: true,
    href: "#"
  }, "Contact your administrator")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 24
    }
  }, /*#__PURE__*/React.createElement(TextInput, {
    id: "login-email",
    labelText: "Email",
    placeholder: "name@company.com",
    light: true
  }), /*#__PURE__*/React.createElement(TextInput, {
    id: "login-pass",
    labelText: "Password",
    type: "password",
    light: true
  }), /*#__PURE__*/React.createElement(Checkbox, {
    id: "login-remember",
    labelText: "Remember me",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Button, {
    renderIcon: "arrow--right",
    onClick: onLogin,
    style: {
      width: '100%',
      maxInlineSize: 'none'
    }
  }, "Log in"))));
}

/* ---------- Dashboard ---------- */
const FIELDS = [{
  id: 'A-12',
  crop: 'Tomato',
  status: ['green', 'Healthy'],
  moisture: '34%',
  temp: '24.3 °C',
  updated: '2 min ago'
}, {
  id: 'A-14',
  crop: 'Lettuce',
  status: ['red', 'Disease risk'],
  moisture: '61%',
  temp: '22.1 °C',
  updated: '5 min ago'
}, {
  id: 'B-02',
  crop: 'Basil',
  status: ['teal', 'Irrigating'],
  moisture: '48%',
  temp: '23.8 °C',
  updated: 'now'
}, {
  id: 'B-07',
  crop: 'Strawberry',
  status: ['green', 'Healthy'],
  moisture: '41%',
  temp: '21.5 °C',
  updated: '1 min ago'
}, {
  id: 'C-01',
  crop: 'Cucumber',
  status: ['gray', 'Idle'],
  moisture: '29%',
  temp: '25.0 °C',
  updated: '12 min ago'
}];
function MetricTile({
  label,
  value,
  delta,
  deltaKind
}) {
  const deltaColor = deltaKind === 'good' ? 'var(--support-success)' : deltaKind === 'bad' ? 'var(--support-error)' : 'var(--text-secondary)';
  return /*#__PURE__*/React.createElement(Tile, {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "type-label-01",
    style: {
      color: 'var(--text-secondary)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--heading-05-size)',
      lineHeight: 'var(--heading-05-lh)',
      fontWeight: 300,
      margin: '8px 0 4px',
      whiteSpace: 'nowrap'
    }
  }, value), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      letterSpacing: '0.32px',
      color: deltaColor
    }
  }, delta));
}
function DashboardScreen({
  onOpenField
}) {
  const [dismissed, setDismissed] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    className: "pc--main"
  }, /*#__PURE__*/React.createElement("p", {
    className: "type-label-01",
    style: {
      margin: 0,
      color: 'var(--text-secondary)'
    }
  }, "Greenhouse Alpha \xB7 Tue, Jul 14"), /*#__PURE__*/React.createElement("h1", {
    className: "type-heading-04",
    style: {
      margin: '4px 0 24px'
    }
  }, "Dashboard"), !dismissed ? /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement(InlineNotification, {
    kind: "warning",
    title: "Sensor N-07 offline.",
    subtitle: "Check the gateway connection in field A-14.",
    onClose: () => setDismissed(true)
  })) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 16,
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement(MetricTile, {
    label: "Monitored zones",
    value: "24",
    delta: "All reporting"
  }), /*#__PURE__*/React.createElement(MetricTile, {
    label: "Avg soil moisture",
    value: "42%",
    delta: "Up 3% vs yesterday",
    deltaKind: "good"
  }), /*#__PURE__*/React.createElement(MetricTile, {
    label: "Open alerts",
    value: "3",
    delta: "Up 1 since 06:00",
    deltaKind: "bad"
  }), /*#__PURE__*/React.createElement(MetricTile, {
    label: "Water used today",
    value: "1,840 L",
    delta: "Down 12% vs plan",
    deltaKind: "good"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 16,
      background: 'var(--layer-01)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--white)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 16px 8px'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
    className: "type-heading-03",
    style: {
      margin: 0
    }
  }, "Fields"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '4px 0 0',
      fontSize: 14,
      color: 'var(--text-secondary)'
    }
  }, "24 monitored zones")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 240
    }
  }, /*#__PURE__*/React.createElement(Search, {
    placeholder: "Search fields",
    size: "md"
  })), /*#__PURE__*/React.createElement(IconButton, {
    icon: "filter",
    label: "Filter"
  }), /*#__PURE__*/React.createElement(Button, {
    size: "md",
    renderIcon: "add"
  }, "Add field"))), /*#__PURE__*/React.createElement(DataTable, {
    size: "md",
    headers: ['Field', 'Crop', 'Status', 'Moisture', 'Temp', 'Updated', ''],
    rows: FIELDS.map(f => [/*#__PURE__*/React.createElement(Link, {
      href: "#",
      onClick: e => {
        e.preventDefault();
        onOpenField(f);
      }
    }, f.id), f.crop, /*#__PURE__*/React.createElement(Tag, {
      type: f.status[0],
      size: "sm"
    }, f.status[1]), f.moisture, f.temp, f.updated, /*#__PURE__*/React.createElement(OverflowMenu, {
      items: [{
        label: 'View detail',
        onClick: () => onOpenField(f)
      }, {
        label: 'Edit'
      }, {
        label: 'Archive',
        danger: true,
        divider: true
      }]
    })])
  }), /*#__PURE__*/React.createElement(Pagination, {
    totalItems: 24,
    pageSizes: [5, 10, 20],
    defaultPageSize: 5
  })))));
}

/* ---------- Field detail ---------- */
function FieldDetailScreen({
  field,
  onBack
}) {
  const [modalOpen, setModalOpen] = React.useState(false);
  const f = field || FIELDS[0];
  return /*#__PURE__*/React.createElement("div", {
    className: "pc--main"
  }, /*#__PURE__*/React.createElement(Breadcrumb, {
    items: [{
      label: 'Fields',
      href: '#'
    }, f.id]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      margin: '8px 0 16px'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h1", {
    className: "type-heading-04",
    style: {
      margin: 0
    }
  }, "Field ", f.id, " \u2014 ", f.crop), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement(Tag, {
    type: f.status[0]
  }, f.status[1]), /*#__PURE__*/React.createElement(Tag, {
    type: "blue"
  }, "Sector 4"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Button, {
    kind: "tertiary",
    size: "md",
    renderIcon: "download"
  }, "Export data"), /*#__PURE__*/React.createElement(Button, {
    kind: "danger--tertiary",
    size: "md",
    onClick: () => setModalOpen(true)
  }, "Archive field"))), /*#__PURE__*/React.createElement(Tabs, {
    tabs: [{
      label: 'Overview',
      panel: /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: 24
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 16
        }
      }, /*#__PURE__*/React.createElement(MetricTile, {
        label: "Soil moisture",
        value: f.moisture,
        delta: "Target 35\u201355%"
      }), /*#__PURE__*/React.createElement(MetricTile, {
        label: "Air temperature",
        value: f.temp,
        delta: "Up 0.8 \xB0C past hour"
      }), /*#__PURE__*/React.createElement(MetricTile, {
        label: "Humidity",
        value: "72%",
        delta: "Stable"
      }), /*#__PURE__*/React.createElement(MetricTile, {
        label: "Canopy health index",
        value: "0.86",
        delta: "Up 0.02 this week",
        deltaKind: "good"
      })), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 16,
          alignItems: 'flex-start'
        }
      }, /*#__PURE__*/React.createElement(Tile, {
        style: {
          flex: 2
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "type-heading-01",
        style: {
          marginBottom: 12
        }
      }, "Irrigation cycle"), /*#__PURE__*/React.createElement(ProgressBar, {
        label: "Zone B pass",
        helperText: "8 of 12 mm applied \xB7 finishes 10:20",
        value: 66
      }), /*#__PURE__*/React.createElement("div", {
        style: {
          marginTop: 16
        }
      }, /*#__PURE__*/React.createElement(Toggle, {
        labelText: "Auto-irrigation",
        defaultToggled: true
      }))), /*#__PURE__*/React.createElement(Tile, {
        style: {
          flex: 1
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "type-heading-01",
        style: {
          marginBottom: 12
        }
      }, "Conditions"), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          fontSize: 14,
          color: 'var(--text-secondary)'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }
      }, /*#__PURE__*/React.createElement(Icon, {
        name: "sun",
        size: 16
      }), " Clear \xB7 UV index 6"), /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }
      }, /*#__PURE__*/React.createElement(Icon, {
        name: "rain",
        size: 16
      }), " No rain expected 48 h"), /*#__PURE__*/React.createElement("span", {
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }
      }, /*#__PURE__*/React.createElement(Icon, {
        name: "humidity",
        size: 16
      }), " Dew point 16 \xB0C")))))
    }, {
      label: 'Sensors',
      panel: /*#__PURE__*/React.createElement(DataTable, {
        size: "md",
        headers: ['Sensor', 'Type', 'Status', 'Last reading', 'Battery'],
        rows: [['N-04', 'Soil moisture', /*#__PURE__*/React.createElement(Tag, {
          type: "green",
          size: "sm"
        }, "Online"), '34% · 09:42', '87%'], ['N-07', 'Soil moisture', /*#__PURE__*/React.createElement(Tag, {
          type: "red",
          size: "sm"
        }, "Offline"), '— · 06:13', '12%'], ['T-02', 'Air temp/RH', /*#__PURE__*/React.createElement(Tag, {
          type: "green",
          size: "sm"
        }, "Online"), '24.3 °C · 09:42', '64%']]
      })
    }, {
      label: 'History',
      panel: /*#__PURE__*/React.createElement("p", {
        style: {
          fontSize: 14,
          color: 'var(--text-secondary)'
        }
      }, "90-day sensor history and imagery timeline.")
    }]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 24
    }
  }, /*#__PURE__*/React.createElement(Button, {
    kind: "ghost",
    size: "md",
    onClick: onBack
  }, "\u2190 Back to dashboard")), /*#__PURE__*/React.createElement(Modal, {
    open: modalOpen,
    danger: true,
    label: 'Field ' + f.id,
    heading: "Archive this field?",
    primaryButtonText: "Archive",
    secondaryButtonText: "Cancel",
    onRequestClose: () => setModalOpen(false),
    onRequestSubmit: () => setModalOpen(false)
  }, "Sensors stay paired but stop reporting. You can restore an archived field from Settings."));
}
Object.assign(window, {
  SideNav,
  LoginScreen,
  DashboardScreen,
  FieldDetailScreen,
  PC_FIELDS: FIELDS
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/plant360-console/screens.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.DataTable = __ds_scope.DataTable;

__ds_ns.Pagination = __ds_scope.Pagination;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.TAG_TYPES = __ds_scope.TAG_TYPES;

__ds_ns.InlineNotification = __ds_scope.InlineNotification;

__ds_ns.Loading = __ds_scope.Loading;

__ds_ns.Modal = __ds_scope.Modal;

__ds_ns.ProgressBar = __ds_scope.ProgressBar;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.RadioButton = __ds_scope.RadioButton;

__ds_ns.RadioButtonGroup = __ds_scope.RadioButtonGroup;

__ds_ns.Search = __ds_scope.Search;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.TextArea = __ds_scope.TextArea;

__ds_ns.TextInput = __ds_scope.TextInput;

__ds_ns.Toggle = __ds_scope.Toggle;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.ICON_NAMES = __ds_scope.ICON_NAMES;

__ds_ns.Accordion = __ds_scope.Accordion;

__ds_ns.Link = __ds_scope.Link;

__ds_ns.OverflowMenu = __ds_scope.OverflowMenu;

__ds_ns.Tile = __ds_scope.Tile;

__ds_ns.Breadcrumb = __ds_scope.Breadcrumb;

__ds_ns.ContentSwitcher = __ds_scope.ContentSwitcher;

__ds_ns.Header = __ds_scope.Header;

__ds_ns.Tabs = __ds_scope.Tabs;

})();
