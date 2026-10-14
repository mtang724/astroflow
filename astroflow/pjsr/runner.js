// astroflow job runner. Job JSON (written by astroflow/pi.py):
// {
//   "input": "<image to process>",            opened as window "main"
//   "aux": {"stars": "<path>"},               extra images opened under these names
//   "linear": true,                           whether "main" is still linear (previews get an AutoSTF)
//   "bgRect": {x0,y0,x1,y1} | null,           background box carried over from earlier jobs
//   "object": {cx, cy, semiMajorPx ...},      the object located by an earlier stage (state.json "object")
//   "steps": [{"op": "...", "optional": false, ...params}],   "each": ["L", "main"] runs a step once per open window
//                                             (as its target; "{window}" in its strings becomes the window's name)
//   "save": [{"window": "main", "path": "...", "bits": 32|16|8}],
//   "previews": [{"window": "main", "path": "...jpg", "size": 1600}],
//   "metrics": [{"window": "main", "path": "...tif", "size": 2048}],
//   "result": "<result json>", "log": "<log file>"
// }

function afForWindow(step, name) {
   var q = {};
   for (var k in step) q[k] = typeof step[k] == "string" ? step[k].replace("{window}", name) : step[k];
   delete q.each;
   q.target = name;
   return q;
}

function astroflowMain(jobPath) {
   var job = JSON.parse(File.readTextFile(jobPath));
   AF.logPath = job.log;
   var result = { ok: false, steps: [], saved: [], previews: [], metrics: [] };
   var ctx = { win: {}, linear: job.linear != false, bgRect: job.bgRect || null, colorCalibrated: !!job.colorCalibrated,
               unscreen: job.unscreen };
   var o = job.object;      // located by an earlier stage (locate_object's info): object-aware steps use it
   if (o && o.semiMajorPx) ctx.object = { cx: o.cx, cy: o.cy, a: o.semiMajorPx, b: o.semiMinorPx, angle: o.angleDeg * Math.PI / 180,
                                          inImage: o.inImage, fillFraction: o.fillFraction };
   var current = null;
   try { console.beginLog(); } catch (e0) {}
   try {
      AF.log("job " + jobPath);
      ctx.win.main = AF.open(job.input, "main");
      var aux = job.aux || {};
      for (var k in aux) ctx.win[k] = AF.open(aux[k], k);
      var steps = job.steps || [];
      for (var i = 0; i < steps.length; ++i) {
         var s = steps[i];
         current = s.op;
         if (!STEPS[s.op]) throw new Error("unknown step " + s.op);
         var t0 = Date.now();
         AF.log("step " + (i + 1) + "/" + steps.length + ": " + s.op);
         var info = null;
         try {
            if (s.each) {
               info = {};
               for (var wi = 0; wi < s.each.length; ++wi)
                  if (ctx.win[s.each[wi]]) info[s.each[wi]] = STEPS[s.op](ctx, afForWindow(s, s.each[wi]));
            } else info = STEPS[s.op](ctx, s);
         }
         catch (e) {
            if (!s.optional) throw e;
            info = { skipped: true, error: e.toString() };
            AF.log("optional step " + s.op + " failed: " + e);
         }
         result.steps.push({ op: s.op, seconds: (Date.now() - t0) / 1000, info: info });
         gc();
      }
      current = "outputs";
      var saves = job.save || [];
      for (i = 0; i < saves.length; ++i) {
         var sv = saves[i];
         var w = ctx.win[sv.window || "main"];
         if (!w) continue;
         AF.saveAs(w, sv.path, sv.bits);
         result.saved.push(sv.path);
      }
      var pvs = job.previews || [];
      for (i = 0; i < pvs.length; ++i) {
         var pv = pvs[i], pw = ctx.win[pv.window || "main"];
         if (!pw) continue;
         var lin = pv.linear == undefined ? (pv.window == "stars" ? false : ctx.linear) : pv.linear;
         var lk = pv.linked == undefined ? ctx.colorCalibrated : pv.linked;   // unlinked STF before colour calibration (video 00:59)
         result.previews.push(AF.savePreview(pw.mainView, pv.path, pv.size || 1600, lin, lk));
      }
      var mts = job.metrics || [];
      for (i = 0; i < mts.length; ++i) {
         var mt = mts[i], mw = ctx.win[mt.window || "main"];
         if (!mw) continue;
         result.metrics.push(AF.saveMetricsTiff(mw.mainView, mt.path, mt.size || 2048));
      }
      var main = ctx.win.main;
      result.stats = AF.stats(main.mainView);
      result.noise = AF.noise(main.mainView);
      result.linear = ctx.linear;
      result.colorCalibrated = ctx.colorCalibrated;
      result.unscreen = ctx.unscreen;
      result.bgRect = ctx.bgRect;
      result.solved = main.hasAstrometricSolution;
      result.windows = Object.keys(ctx.win);
      result.ok = true;
      AF.log("job done");
   } catch (e) {
      result.error = "[" + current + "] " + e.toString();
      result.stack = e.stack || "";
      AF.log("ERROR " + result.error);
   }
   try {
      var consoleText = console.endLog();
      File.writeTextFile(job.log.replace(/[^\/]+$/, "console.txt"), String(consoleText));
   } catch (e1) {}
   File.writeTextFile(job.result, JSON.stringify(result, null, 1));
   var ws = ImageWindow.windows;
   for (var j = 0; j < ws.length; ++j) ws[j].forceClose();
}
