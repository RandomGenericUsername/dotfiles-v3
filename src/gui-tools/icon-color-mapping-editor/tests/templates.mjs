// Unit tests for lib/templates.ts. Run with plain node:
// `node tests/templates.mjs` from the tool directory.
import {
  applyTemplateEdit,
  bareProgress,
  buildTreeEntries,
  describeTemplatePending,
  groupAndLabel,
  isValidPlaceholderName,
  mappingsForTemplate,
  modeOf,
  paintValueOf,
  renderPreviewBody,
  resolveColorHex,
  stageTemplateEdit,
  templatePathsFrom,
  templatePendingKey,
  workingFrom,
} from "../lib/templates.ts";

let failures = 0;
function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    failures += 1;
    console.error(`FAIL ${name}\n  expected: ${e}\n  actual:   ${a}`);
  } else {
    console.log(`ok ${name}`);
  }
}

const SHAPE = {
  id: 1,
  tag: "path",
  paintAttr: "fill",
  placeholder: "COLOR_FOREGROUND",
  literal: null,
};

check("pending key", templatePendingKey("/a/b.svg", 3), "/a/b.svg\u00003");
check("pending key distinct", templatePendingKey("/a/b.svg", 3) !== templatePendingKey("/a/b.svg", 4), true);
check("working from placeholder", workingFrom(SHAPE), {
  id: 1, tag: "path", attr: "fill", ph: "COLOR_FOREGROUND", literal: null,
});
check("paint value placeholder", paintValueOf(workingFrom(SHAPE)), "{{COLOR_FOREGROUND}}");
check("paint value literal", paintValueOf({ id: 1, tag: "rect", attr: "fill", ph: null, literal: "#c2c2c5" }), "#c2c2c5");

const bare = [
  { id: 1, tag: "path", attr: "fill", ph: null, literal: "#c2c2c5" },
  { id: 2, tag: "rect", attr: "fill", ph: null, literal: "#ffffff" },
];
const templated = [
  { id: 1, tag: "path", attr: "stroke", ph: "COLOR_FOREGROUND", literal: null },
  { id: 2, tag: "rect", attr: "fill", ph: "COLOR_FOREGROUND", literal: null },
];

check("bare progress", bareProgress(bare), { assigned: 0, total: 2 });
check("partial progress", bareProgress([{ ...bare[0], ph: "X" }, bare[1]]), { assigned: 1, total: 2 });
check("mode templated", modeOf(templated), "templated");
check("mode bare", modeOf(bare), "bare");
check("mode zero shapes", modeOf([]), "bare");

check("valid names", ["COLOR_FOREGROUND", "A", "COLOR_1", "X_Y_Z"].every(isValidPlaceholderName), true);
check("invalid names", ["color contour", "1A", "color", "A-B", ""].some(isValidPlaceholderName), false);

check("group status-bar", groupAndLabel("/r/status-bar/battery/battery-25/default/icon.svg", "/r"), {
  group: "battery", label: "battery-25/default",
});
check("group power-menu", groupAndLabel("/r/status-bar/power-menu/default/icon.svg", "/r"), {
  group: "power-menu", label: "default",
});
check("group shorth path", groupAndLabel("/r/screen-recorder/default/play.svg", "/r"), {
  group: "default", label: "play.svg",
});

const modes = new Map([
  ["/r/status-bar/battery/battery-25/default/icon.svg", "templated"],
  ["/r/status-bar/battery/battery-unplugged/default/icon.svg", "bare"],
  ["/r/status-bar/power-menu/default/icon.svg", "templated"],
]);
const tree = buildTreeEntries("/r", modes);
check("tree groups sorted", tree.map((e) => e.group), ["battery", "battery", "power-menu"]);
check("tree labels", tree.map((e) => e.label), ["battery-25/default", "battery-unplugged/default", "default"]);
check("tree modes", tree.map((e) => e.mode), ["templated", "bare", "templated"]);

const SHOW = {
  groups: [
    {
      group: "battery",
      variants: [
        {
          variant: "battery-0",
          template_path: "/r/status-bar/battery/battery-0/default/icon.svg",
          svg_body: "<svg/>",
          mappings: [
            { placeholder: "COLOR_FOREGROUND", token: "color6", origin: "group" },
            { placeholder: "COLOR_ACCENT", token: "color12", origin: "group" },
          ],
        },
      ],
    },
  ],
  palette: { color6: "#e0e0e0" },
  missing_tokens: [],
  shadows: {},
};

check("template paths from show", templatePathsFrom(SHOW), ["/r/status-bar/battery/battery-0/default/icon.svg"]);
check("template paths null", templatePathsFrom(null), []);
check(
  "mappings for template",
  mappingsForTemplate(SHOW, "/r/status-bar/battery/battery-0/default/icon.svg", new Map([["COLOR_COUNTOUR", "color5"]])),
  { COLOR_FOREGROUND: "color6", COLOR_ACCENT: "color12", COLOR_COUNTOUR: "color5" },
);
check("mappings foreign template", mappingsForTemplate(SHOW, "/other.svg", new Map()), {});

const edit = {
  templatePath: "/r/status-bar/battery/battery-0/default/icon.svg",
  shapeId: 1,
  attr: "fill",
  oldValue: "{{COLOR_FOREGROUND}}",
  newPlaceholder: "COLOR_COUNTOUR",
};
const staged = stageTemplateEdit(new Map(), edit);
check("stage adds edit", staged.size, 1);
check("stage key", staged.has(templatePendingKey(edit.templatePath, edit.shapeId)), true);
const applied = applyTemplateEdit(templated, edit);
check("apply sets ph", applied[0].ph, "COLOR_COUNTOUR");
check("apply clears literal", applied[0].literal, null);
check("apply leaves other", applied[1].ph, "COLOR_FOREGROUND");

const workingByPath = new Map([
  [edit.templatePath, templated],
]);
const rows = describeTemplatePending({
  templatePendings: staged,
  newPlaceholders: new Map([["COLOR_COUNTOUR", "color5"]]),
  manifestPendings: [
    {
      manifestPath: "/m/icons.yaml",
      group: "screenshot-tool",
      variant: "cursor",
      template: "screenshot-tool/cursor/default/cursor.svg",
      output: "cursor.svg",
    },
  ],
  workingByPath,
});
check("template row header", rows[0].header, edit.templatePath);
check(
  "template row html",
  rows[0].html,
  '  -  <path … fill="{{COLOR_FOREGROUND}}"/>' + String.fromCharCode(10) + '  +  <path … fill="{{COLOR_COUNTOUR}}"/>',
);
check("defaults row header", rows[1].header, "defaults.yaml → defaults");
check("defaults row html", rows[1].html, "  +   COLOR_COUNTOUR: color5");
check("manifest row header", rows[2].header, "/m/icons.yaml → screenshot-tool");
check(
  "manifest row html",
  rows[2].html,
  "  +   - name: cursor" + String.fromCharCode(10) + "      template: screenshot-tool/cursor/default/cursor.svg" + String.fromCharCode(10) + "      output: cursor.svg",
);

// resolve + preview body rendering
const palette = { color6: "#e0e0e0", color5: "#a67fc0" };
check("resolve placeholder", resolveColorHex({ id: 1, tag: "path", attr: "fill", ph: "COLOR_FOREGROUND", literal: null }, { COLOR_FOREGROUND: "color6" }, palette), "#e0e0e0");
check("resolve literal", resolveColorHex({ id: 1, tag: "path", attr: "fill", ph: null, literal: "#c2c2c5" }, {}, palette), "#c2c2c5");
check("resolve unresolved", resolveColorHex({ id: 1, tag: "path", attr: "fill", ph: "GHOST", literal: null }, {}, palette), null);

const BODY = '<svg fill="none"><rect fill="{{COLOR_FOREGROUND}}" x="0" y="0" width="1" height="1"/><path d="M0 0H1" stroke="{{COLOR_FOREGROUND}}"/></svg>';
const bodyShapes = [
  { id: 1, tag: "rect", attr: "fill", ph: "COLOR_FOREGROUND", literal: null },
  { id: 2, tag: "path", attr: "stroke", ph: "COLOR_COUNTOUR", literal: null },
];
const rendered = renderPreviewBody(BODY, bodyShapes, (s) => (s.ph ? `{{${s.ph}}}` : s.literal));
check("preview rewrites fill", rendered.includes('fill="{{COLOR_FOREGROUND}}"'), true);
check("preview rewrites stroke", rendered.includes('stroke="{{COLOR_COUNTOUR}}"'), true);
check("preview preserves other attrs", rendered.includes('x="0"'), true);

// re-assign keeps the original oldValue
const first = stageTemplateEdit(new Map(), edit);
const second = stageTemplateEdit(first, { ...edit, newPlaceholder: "COLOR_SECOND" });
check("re-assign keeps oldValue", second.get(templatePendingKey(edit.templatePath, edit.shapeId)).oldValue, "{{COLOR_FOREGROUND}}");
check("re-assign updates target", second.get(templatePendingKey(edit.templatePath, edit.shapeId)).newPlaceholder, "COLOR_SECOND");

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("template cases agree");
}
