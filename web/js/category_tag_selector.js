import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const NODE_CLASS = "CategoryTagSelector";
const LEGACY_PREFIX = "cts::";

function cleanLabel(name) {
  const value = String(name ?? "");
  return value.startsWith(LEGACY_PREFIX)
    ? value.slice(LEGACY_PREFIX.length)
    : value;
}

function findWidget(node, name) {
  return node.widgets?.find((w) => w.name === name);
}

function hideWidget(widget) {
  if (!widget) return;

  widget.hidden = true;
  widget.computeSize = () => [0, 0];
  widget.draw = () => {};

  for (const key of ["inputEl", "element", "domElement"]) {
    const el = widget[key];
    if (el?.style) {
      el.style.display = "none";
      el.style.visibility = "hidden";
      el.style.height = "0px";
      el.style.minHeight = "0px";
      el.style.maxHeight = "0px";
      el.style.margin = "0px";
      el.style.padding = "0px";
    }
  }
}

function parseSelections(node) {
  const widget = findWidget(node, "selections_json");
  if (!widget) return {};

  try {
    const parsed = JSON.parse(widget.value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

function writeSelections(node, selections) {
  const widget = findWidget(node, "selections_json");
  if (!widget) return;

  widget.value = JSON.stringify(selections, null, 0);
  hideWidget(widget);
}

function isCategoryWidget(widget) {
  const name = String(widget?.name ?? "");
  return widget?.ctsDynamic === true || name.startsWith(LEGACY_PREFIX);
}

function removeCategoryWidgets(node) {
  if (!node.widgets) return;
  node.widgets = node.widgets.filter((widget) => !isCategoryWidget(widget));
}

function resizeNode(node) {
  try {
    const size = node.computeSize();
    node.setSize([Math.max(size[0], 320), size[1]]);
    app.graph.setDirtyCanvas(true, true);
  } catch (error) {
    console.warn("[Category Tag Selector] resize failed:", error);
  }
}

async function refreshYamlFileList(node) {
  const yamlWidget = findWidget(node, "yaml_file");
  if (!yamlWidget) return;

  const oldValue = String(yamlWidget.value ?? "");

  try {
    const response = await api.fetchApi("/category_tag_selector/yamls");
    const data = await response.json();
    const files = Array.isArray(data.files) ? data.files : [];

    if (!files.length) return;

    yamlWidget.options ??= {};
    yamlWidget.options.values = files;

    if (files.includes(oldValue)) {
      yamlWidget.value = oldValue;
    } else {
      yamlWidget.value = files[0];
      writeSelections(node, {});
    }
  } catch (error) {
    console.error("[Category Tag Selector] yaml list fetch failed:", error);
  }
}

async function loadSchema(node) {
  const yamlWidget = findWidget(node, "yaml_file");
  const yamlFile = yamlWidget?.value;
  if (!yamlFile) return;

  const seq = (node._ctsLoadSeq = (node._ctsLoadSeq ?? 0) + 1);

  const saved = parseSelections(node);
  hideWidget(findWidget(node, "selections_json"));

  let schema;

  try {
    const response = await api.fetchApi(
      `/category_tag_selector/schema?file=${encodeURIComponent(yamlFile)}`
    );
    schema = await response.json();
  } catch (error) {
    if (seq === node._ctsLoadSeq) {
      console.error("[Category Tag Selector] schema fetch failed:", error);
      removeCategoryWidgets(node);
      resizeNode(node);
    }
    return;
  }

  if (seq !== node._ctsLoadSeq) return;

  removeCategoryWidgets(node);

  if (schema.error) {
    console.error("[Category Tag Selector]", schema.error);
    writeSelections(node, {});
    resizeNode(node);
    return;
  }

  const nextSelections = {};
  const seenCategories = new Set();

  for (const category of schema.categories || []) {
    const categoryName = cleanLabel(category.name);

    if (!categoryName || seenCategories.has(categoryName)) continue;
    seenCategories.add(categoryName);

    const rawOptions = Array.isArray(category.options) ? category.options : [];
    const options = [...new Set(rawOptions.map(cleanLabel).filter(Boolean))];
    const values = options.length ? options : ["なし"];

    const current = values.includes(saved[categoryName])
      ? saved[categoryName]
      : values[0];

    nextSelections[categoryName] = current;

    const widget = node.addWidget(
      "combo",
      categoryName,
      current,
      (value) => {
        const selections = parseSelections(node);
        selections[categoryName] = value;
        writeSelections(node, selections);
      },
      { values }
    );

    widget.ctsDynamic = true;
    widget.ctsCategoryName = categoryName;
  }

  writeSelections(node, nextSelections);
  hideWidget(findWidget(node, "selections_json"));
  resizeNode(node);
}

function scheduleLoadSchema(node, delay = 100) {
  clearTimeout(node._ctsLoadTimer);
  node._ctsLoadTimer = setTimeout(() => loadSchema(node), delay);
}

function addRefreshButton(node) {
  if (node._ctsRefreshButtonAdded) return;

  node._ctsRefreshButtonAdded = true;

  const refreshWidget = node.addWidget(
    "button",
    "Refresh YAML Files",
    null,
    () => {
      refreshYamlFileList(node).finally(() => {
        writeSelections(node, {});
        scheduleLoadSchema(node, 0);
      });
    }
  );

  refreshWidget.ctsControl = true;
}

app.registerExtension({
  name: "nobin.categoryTagSelector",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_CLASS) return;

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = originalOnNodeCreated?.apply(this, arguments);

      removeCategoryWidgets(this);
      hideWidget(findWidget(this, "selections_json"));

      const yamlWidget = findWidget(this, "yaml_file");

      if (yamlWidget && !yamlWidget._ctsPatched) {
        yamlWidget._ctsPatched = true;

        const originalCallback = yamlWidget.callback;

        yamlWidget.callback = (value) => {
          originalCallback?.call(yamlWidget, value);
          writeSelections(this, {});
          scheduleLoadSchema(this, 0);
        };
      }

      addRefreshButton(this);

      refreshYamlFileList(this).finally(() => {
        scheduleLoadSchema(this, 100);
      });

      return result;
    };

    const originalOnConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = originalOnConfigure?.apply(this, arguments);

      for (const widget of this.widgets ?? []) {
        if (String(widget.name ?? "").startsWith(LEGACY_PREFIX)) {
          widget.name = cleanLabel(widget.name);
          widget.ctsDynamic = true;
        }
      }

      removeCategoryWidgets(this);
      hideWidget(findWidget(this, "selections_json"));

      refreshYamlFileList(this).finally(() => {
        scheduleLoadSchema(this, 100);
      });

      return result;
    };
  },
});