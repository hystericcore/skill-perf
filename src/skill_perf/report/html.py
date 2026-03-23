"""Generate a standalone HTML report with an interactive D3.js treemap."""


import json
from pathlib import Path

from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.report.treemap import build_treemap

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>skill-perf Report</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",
  Roboto,Helvetica,Arial,sans-serif;background:#f5f5f5;color:#333}
#header{background:#1a1a2e;color:#fff;padding:12px 24px;
  display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:12px}
#header h1{font-size:1.25rem;font-weight:600;letter-spacing:.02em}
#controls{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
#controls label{font-size:.85rem;cursor:pointer;display:flex;align-items:center;gap:4px}
#controls input[type=radio]{accent-color:#4A90D9}
#search{padding:6px 10px;border:1px solid #555;
  border-radius:4px;background:#2a2a3e;color:#fff;
  font-size:.85rem;width:180px}
#search::placeholder{color:#999}
#main{display:flex;height:calc(100vh - 56px)}
#treemap{flex:1;position:relative;overflow:hidden;background:#fff}
#breadcrumb{position:absolute;top:8px;left:8px;z-index:10;display:flex;gap:4px;flex-wrap:wrap}
.crumb{background:#1a1a2e;color:#fff;padding:3px 8px;
  border-radius:3px;font-size:.75rem;cursor:pointer;border:none}
.crumb:hover{background:#4A90D9}
#sidebar{width:320px;background:#fff;border-left:1px solid #ddd;
  overflow-y:auto;padding:16px;font-size:.85rem}
#sidebar h2{font-size:1rem;margin-bottom:8px;border-bottom:1px solid #eee;padding-bottom:4px}
#sidebar h3{font-size:.9rem;margin:12px 0 6px;color:#555}
.meta-row{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #f0f0f0}
.meta-label{color:#777}
.meta-value{font-weight:600}
.issue-item{padding:6px 0;border-bottom:1px solid #f0f0f0;cursor:pointer}
.issue-item:hover{background:#f9f9f9}
.issue-sev{margin-right:4px}
.issue-pattern{font-weight:600;font-size:.8rem}
.issue-desc{color:#666;font-size:.78rem;margin-top:2px}
.dist-table{width:100%;border-collapse:collapse;font-size:.8rem}
.dist-table th,.dist-table td{padding:4px 6px;text-align:left;border-bottom:1px solid #f0f0f0}
.dist-table th{color:#777;font-weight:500}
.dist-bar{height:6px;border-radius:3px;margin-top:2px}
.tooltip{position:absolute;background:rgba(26,26,46,.95);
  color:#fff;padding:8px 12px;border-radius:4px;
  font-size:.78rem;pointer-events:none;z-index:100;
  max-width:280px;line-height:1.4}
@media(max-width:768px){
  #main{flex-direction:column}
  #sidebar{width:100%;max-height:40vh;border-left:none;border-top:1px solid #ddd}
}
</style>
</head>
<body>
<div id="header">
  <h1>skill-perf Report</h1>
  <div id="controls">
    <label><input type="radio" name="size" value="token_count" checked> Raw Tokens</label>
    <label><input type="radio" name="size" value="effective_tokens"> Effective Tokens</label>
    <label><input type="radio" name="size" value="cost_usd"> Estimated Cost</label>
    <input id="search" type="text" placeholder="Search files, tools...">
  </div>
</div>
<div id="main">
  <div id="treemap">
    <div id="breadcrumb"></div>
  </div>
  <div id="sidebar">
    <h2>Session Info</h2>
    <div id="session-meta"></div>
    <h3>Issues</h3>
    <div id="issues-list"></div>
    <h3>Token Distribution</h3>
    <div id="token-dist"></div>
  </div>
</div>
<script>
const DATA = __TREEMAP_DATA__;
const ISSUES = __ISSUES_DATA__;
const SESSION = __SESSION_DATA__;

const COLORS = {
  system_prompt: "#4A90D9",
  tool_result: "#F5A623",
  skill_load: "#7ED321",
  assistant_response: "#9B59B6",
  tool_call: "#3498DB",
  user_message: "#95A5A6",
  waste: "#E74C3C",
  session: "#BDC3C7"
};

function nodeColor(d) {
  if (d.data.is_wasteful) return COLORS.waste;
  return COLORS[d.data.category] || "#BDC3C7";
}

// --- Sidebar ---
(function renderSidebar() {
  const meta = document.getElementById("session-meta");
  const rows = [
    ["Model", SESSION.model],
    ["Total Tokens", SESSION.total_estimated_tokens.toLocaleString()],
    ["API Input", SESSION.api_input_tokens.toLocaleString()],
    ["API Output", SESSION.api_output_tokens.toLocaleString()],
    ["Think/Act Ratio", SESSION.think_act_ratio.toFixed(2)],
    ["Waste", SESSION.waste_percentage.toFixed(1) + "%"]
  ];
  meta.innerHTML = rows.map(function(r) {
    return '<div class="meta-row"><span class="meta-label">'
      + r[0] + '</span><span class="meta-value">'
      + r[1] + '</span></div>';
  }).join("");

  const il = document.getElementById("issues-list");
  if (!ISSUES.length) { il.innerHTML = "<p style='color:#999'>No issues found.</p>"; }
  else {
    il.innerHTML = ISSUES.map(function(iss, idx) {
      var sev = iss.severity === "critical"
        ? "\\uD83D\\uDD34" : iss.severity === "warning"
        ? "\\uD83D\\uDFE1" : "\\uD83D\\uDFE2";
      return '<div class="issue-item" data-step="'
        + iss.step_index + '" data-idx="' + idx + '">'
        + '<span class="issue-sev">' + sev + '</span>'
        + '<span class="issue-pattern">'
        + iss.pattern + '</span>'
        + '<div class="issue-desc">' + iss.description
        + ' (' + iss.impact_tokens
        + ' tokens)</div></div>';
    }).join("");
  }

  var byType = SESSION.tokens_by_type || {};
  var total = SESSION.total_estimated_tokens || 1;
  var dist = document.getElementById("token-dist");
  var thead = "<table class='dist-table'><tr><th>Category</th><th>Tokens</th><th>%</th></tr>";
  var tbody = Object.keys(byType).map(function(k) {
    var pct = (byType[k] / total * 100).toFixed(1);
    var col = COLORS[k] || "#BDC3C7";
    return "<tr><td>" + k + "</td><td>" + byType[k].toLocaleString() + "</td><td>" + pct
      + '%<div class="dist-bar" style="width:' + pct + '%;background:' + col + '"></div></td></tr>';
  }).join("");
  dist.innerHTML = thead + tbody + "</table>";
})();

// --- Treemap ---
var sizeKey = "token_count";
var container = document.getElementById("treemap");
var width, height;
var currentRoot;
var tooltip = d3.select("body").append("div").attr("class", "tooltip").style("display", "none");

function getSize() {
  var rect = container.getBoundingClientRect();
  width = rect.width;
  height = rect.height - 30;
}

function buildHierarchy(data) {
  return d3.hierarchy(data)
    .sum(function(d) { return d.children && d.children.length ? 0 : Math.max(d[sizeKey], 0.001); })
    .sort(function(a, b) { return b.value - a.value; });
}

function renderBreadcrumb(node) {
  var path = [];
  var n = node;
  while (n) { path.unshift(n); n = n.parent; }
  var bc = document.getElementById("breadcrumb");
  bc.innerHTML = "";
  path.forEach(function(p) {
    var btn = document.createElement("button");
    btn.className = "crumb";
    btn.textContent = p.data.name;
    btn.onclick = function() { zoomTo(p); };
    bc.appendChild(btn);
  });
}

function zoomTo(node) {
  currentRoot = node;
  render(node);
  renderBreadcrumb(node);
}

function render(root) {
  getSize();
  var treemapLayout = d3.treemap().size([width, height]).paddingInner(2).paddingTop(20).round(true);
  var hier = buildHierarchy(root.data);
  treemapLayout(hier);

  var svg = d3.select("#treemap").selectAll("svg").data([0]);
  svg = svg.enter().append("svg").merge(svg);
  svg.attr("width", width).attr("height", height)
    .style("position", "absolute")
    .style("top", "30px").style("left", "0");

  var leaves = hier.leaves();

  var groups = svg.selectAll("g.cell").data(leaves, function(d) { return d.data.name + d.depth; });
  groups.exit().remove();
  var enter = groups.enter().append("g").attr("class", "cell");
  enter.append("rect");
  enter.append("text");
  var merged = enter.merge(groups);

  merged.attr("transform", function(d) { return "translate(" + d.x0 + "," + d.y0 + ")"; });

  merged.select("rect")
    .attr("width", function(d) { return Math.max(0, d.x1 - d.x0); })
    .attr("height", function(d) { return Math.max(0, d.y1 - d.y0); })
    .attr("fill", function(d) { return nodeColor(d); })
    .attr("stroke", "#fff")
    .attr("stroke-width", 1)
    .style("cursor", "pointer")
    .on("click", function(ev, d) {
      // find matching node in currentRoot to zoom
      var match = findNode(currentRoot, d.data.name);
      if (match && match.children && match.children.length) {
        zoomTo(match);
      }
    })
    .on("mouseover", function(ev, d) {
      var html = "<strong>" + d.data.name + "</strong><br>"
        + "Tokens: " + d.data.token_count.toLocaleString() + "<br>"
        + "Effective: " + d.data.effective_tokens.toLocaleString() + "<br>"
        + "Cost: $" + d.data.cost_usd.toFixed(6) + "<br>"
        + "Category: " + d.data.category;
      if (d.data.issues && d.data.issues.length) {
        html += "<br><strong style='color:#E74C3C'>" + d.data.issues.length + " issue(s)</strong>";
      }
      tooltip.html(html).style("display", "block");
    })
    .on("mousemove", function(ev) {
      tooltip.style("left", (ev.pageX + 12) + "px").style("top", (ev.pageY - 12) + "px");
    })
    .on("mouseout", function() { tooltip.style("display", "none"); });

  merged.select("text")
    .attr("x", 4).attr("y", 14)
    .text(function(d) {
      var w = d.x1 - d.x0;
      if (w < 40) return "";
      var name = d.data.name;
      var maxChars = Math.floor(w / 7);
      return name.length > maxChars ? name.slice(0, maxChars - 1) + "\\u2026" : name;
    })
    .attr("font-size", "11px")
    .attr("fill", "#fff")
    .style("pointer-events", "none");

  // Group labels
  var internal = hier.descendants().filter(function(d) { return d.children; });
  var glabels = svg.selectAll("text.group-label")
    .data(internal, function(d) { return "g-" + d.data.name; });
  glabels.exit().remove();
  var glEnter = glabels.enter().append("text").attr("class", "group-label");
  glEnter.merge(glabels)
    .attr("x", function(d) { return d.x0 + 4; })
    .attr("y", function(d) { return d.y0 + 14; })
    .text(function(d) { return d.data.name; })
    .attr("font-size", "12px")
    .attr("font-weight", "600")
    .attr("fill", "#333")
    .style("pointer-events", "none");
}

function findNode(node, name) {
  if (!node.children) return null;
  for (var i = 0; i < node.children.length; i++) {
    if (node.children[i].data.name === name) return node.children[i];
    var found = findNode(node.children[i], name);
    if (found) return found;
  }
  return null;
}

// Initial render
var rootHier = d3.hierarchy(DATA);
currentRoot = rootHier;
render(rootHier);
renderBreadcrumb(rootHier);

// Size toggle
document.querySelectorAll('input[name="size"]').forEach(function(radio) {
  radio.addEventListener("change", function() {
    sizeKey = this.value;
    render(currentRoot);
  });
});

// Search
document.getElementById("search").addEventListener("input", function() {
  var q = this.value.toLowerCase();
  d3.selectAll("#treemap g.cell rect").attr("opacity", function(d) {
    if (!q) return 1;
    var text = (d.data.name + " " + d.data.category).toLowerCase();
    return text.indexOf(q) >= 0 ? 1 : 0.2;
  });
});

// Issue click highlight
document.querySelectorAll(".issue-item").forEach(function(el) {
  el.addEventListener("click", function() {
    var step = parseInt(this.dataset.step);
    d3.selectAll("#treemap g.cell rect")
      .attr("stroke", function(d) {
        return d.data.issues && d.data.issues.some(function(i) { return i.step_index === step; })
          ? "#E74C3C" : "#fff";
      })
      .attr("stroke-width", function(d) {
        return d.data.issues && d.data.issues.some(function(i) { return i.step_index === step; })
          ? 3 : 1;
      });
  });
});

// Resize
window.addEventListener("resize", function() { render(currentRoot); });
</script>
</body>
</html>
"""


def generate_html_report(
    session: SessionAnalysis,
    issues: list[Issue],
    output_path: str | None = None,
    model: str = "claude-sonnet-4",
) -> str:
    """Generate standalone HTML file with interactive treemap.

    Returns the HTML string. If *output_path* is given, also writes to file.
    """
    tree = build_treemap(session, model=model)
    treemap_json = tree.model_dump_json()

    issues_json = json.dumps([i.model_dump() for i in issues])

    session_meta = {
        "session_id": session.session_id,
        "model": session.model,
        "api_input_tokens": session.api_input_tokens,
        "api_output_tokens": session.api_output_tokens,
        "total_estimated_tokens": session.total_estimated_tokens,
        "tokens_by_type": session.tokens_by_type,
        "tokens_by_tool": session.tokens_by_tool,
        "think_act_ratio": session.think_act_ratio,
        "waste_tokens": session.waste_tokens,
        "waste_percentage": session.waste_percentage,
    }
    session_json = json.dumps(session_meta)

    html = _HTML_TEMPLATE
    html = html.replace("__TREEMAP_DATA__", treemap_json)
    html = html.replace("__ISSUES_DATA__", issues_json)
    html = html.replace("__SESSION_DATA__", session_json)

    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")

    return html
