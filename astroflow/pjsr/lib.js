// astroflow PJSR helpers: logging, statistics, previews, background search, stretches.
// Loaded by the bootstrap generated in astroflow/pi.py (after ImageSolver.js and friends).

var AF = AF || {};

AF.logPath = null;

AF.log = function (msg) {
   var line = (new Date()).toISOString() + " " + msg;
   console.writeln("[astroflow] " + msg);
   if (AF.logPath) {
      try {
         var f = new File;
         if (File.exists(AF.logPath)) { f.openForReadWrite(AF.logPath); f.seekEnd(); }
         else f.createForWriting(AF.logPath);
         f.outTextLn(line);
         f.close();
      } catch (e) { console.warningln("log failed: " + e); }
   }
};

AF.windowById = function (id) {
   var w = ImageWindow.windowById(id);
   if (w == null || w.isNull) throw new Error("No image window with id " + id);
   return w;
};

AF.open = function (path, id) {
   var ws = ImageWindow.open(path);
   if (ws.length == 0) throw new Error("Cannot open " + path);
   var w = ws[0];
   for (var i = 1; i < ws.length; ++i) ws[i].forceClose();
   if (id) w.mainView.id = id;
   w.hide();
   return w;
};

AF.windowIds = function () {
   var ids = {};
   var ws = ImageWindow.windows;
   for (var i = 0; i < ws.length; ++i) ids[ws[i].mainView.id] = true;
   return ids;
};

// Windows created since `before` (an AF.windowIds() snapshot).
AF.newWindows = function (before) {
   var out = [];
   var ws = ImageWindow.windows;
   for (var i = 0; i < ws.length; ++i)
      if (!before[ws[i].mainView.id]) out.push(ws[i]);
   return out;
};

AF.round = function (x, n) { var p = Math.pow(10, n || 6); return Math.round(x * p) / p; };

// Per-channel statistics of a view (optionally inside a rectangle).
AF.stats = function (view, rect) {
   var img = view.image;
   var out = { width: img.width, height: img.height, channels: img.numberOfChannels, median: [], mad: [], mean: [], min: [], max: [] };
   for (var c = 0; c < img.numberOfChannels; ++c) {
      img.resetSelections();
      img.selectedChannel = c;
      if (rect) img.selectedRect = rect;
      var med = img.median();
      out.median.push(AF.round(med, 7));
      out.mad.push(AF.round(img.MAD(med), 7));
      out.mean.push(AF.round(img.mean(), 7));
      out.min.push(AF.round(img.minimum(), 7));
      out.max.push(AF.round(img.maximum(), 7));
   }
   img.resetSelections();
   return out;
};

// Gaussian noise estimate per channel (multiresolution support, falls back to k-sigma).
AF.noise = function (view) {
   var img = view.image, out = [];
   for (var c = 0; c < img.numberOfChannels; ++c) {
      img.resetSelections();
      img.selectedChannel = c;
      var s = 0;
      try { var a = img.noiseMRS(4); s = a[0]; if (!(s > 0)) throw 0; }
      catch (e) { try { s = img.noiseKSigma()[0]; } catch (e2) { s = -1; } }
      out.push(AF.round(s, 8));
   }
   img.resetSelections();
   return out;
};

// ---------------------------------------------------------------------------
// Midtones transfer helpers
// ---------------------------------------------------------------------------

// Midtones balance m such that HT maps x -> target (closed form of the MTF inverse).
AF.mtfFor = function (x, target) {
   if (x <= 0) return 0.5;
   if (x >= 1) return 0.5;
   return (target - 1) * x / ((2 * target - 1) * x - target);
};

// Standard PixInsight AutoSTF parameters (shadows clip -2.8 MAD, target background 0.25).
AF.autoSTF = function (view, linked, targetBkg, shadowsClip) {
   targetBkg = targetBkg || 0.25;
   shadowsClip = shadowsClip || -2.8;
   var st = AF.stats(view);
   var n = st.channels, H = [];
   var c0s = [], ms = [];
   for (var c = 0; c < n; ++c) {
      var med = st.median[c], mad = st.mad[c] * 1.4826;
      var c0 = (mad == 0) ? 0 : Math.range(med + shadowsClip * mad, 0, 1);
      c0s.push(c0);
      ms.push(AF.mtfFor(med - c0, targetBkg));
   }
   if (linked && n == 3) {
      var c0m = (c0s[0] + c0s[1] + c0s[2]) / 3;
      var medm = (st.median[0] + st.median[1] + st.median[2]) / 3;
      var mm = AF.mtfFor(medm - c0m, targetBkg);
      c0s = [c0m, c0m, c0m]; ms = [mm, mm, mm];
   }
   return { c0: c0s, m: ms };
};

AF.applyHT = function (view, c0s, ms, c1s) {
   var HT = new HistogramTransformation;
   var H = [[0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1]];
   if (view.image.numberOfChannels == 1) H[3] = [c0s[0], ms[0], c1s ? c1s[0] : 1, 0, 1];
   else for (var c = 0; c < 3; ++c) H[c] = [c0s[c], ms[c], c1s ? c1s[c] : 1, 0, 1];
   HT.H = H;
   HT.executeOn(view, false);
};

// ---------------------------------------------------------------------------
// Copies, previews and exports
// ---------------------------------------------------------------------------

AF.duplicate = function (view, id, scale, bits, float) {
   var src = view.image;
   var win = new ImageWindow(src.width, src.height, src.numberOfChannels, bits || 32, float == undefined ? true : float,
                             src.isColor, id || "af_tmp");
   win.mainView.beginProcess(UndoFlag_NoSwapFile);
   win.mainView.image.assign(src);
   if (scale && scale != 1) win.mainView.image.resample(scale);
   win.mainView.endProcess();
   win.hide();
   return win;
};

// Save a JPG preview. Linear images get an AutoSTF stretch on the copy (linked by default).
AF.savePreview = function (view, path, maxSize, linear, linked) {
   var img = view.image;
   var scale = Math.min(1, (maxSize || 1600) / Math.max(img.width, img.height));
   var tmp = AF.duplicate(view, "af_preview", scale);
   if (linear) {
      var p = AF.autoSTF(tmp.mainView, linked != false);
      AF.applyHT(tmp.mainView, p.c0, p.m);
   }
   var out8 = new ImageWindow(tmp.mainView.image.width, tmp.mainView.image.height, tmp.mainView.image.numberOfChannels,
                              8, false, tmp.mainView.image.isColor, "af_preview8");
   out8.mainView.beginProcess(UndoFlag_NoSwapFile);
   out8.mainView.image.assign(tmp.mainView.image);
   out8.mainView.endProcess();
   out8.saveAs(path, false, false, false, false, "quality 92");
   out8.forceClose();
   tmp.forceClose();
   return path;
};

// Downsampled 16-bit linear-value TIFF for numeric metrics in Python (no stretch applied).
AF.saveMetricsTiff = function (view, path, maxSize) {
   var img = view.image;
   var scale = Math.min(1, (maxSize || 2048) / Math.max(img.width, img.height));
   var tmp = AF.duplicate(view, "af_metrics", scale);
   var w16 = new ImageWindow(tmp.mainView.image.width, tmp.mainView.image.height, tmp.mainView.image.numberOfChannels,
                             16, false, tmp.mainView.image.isColor, "af_metrics16");
   w16.mainView.beginProcess(UndoFlag_NoSwapFile);
   w16.mainView.image.assign(tmp.mainView.image);
   w16.mainView.endProcess();
   w16.saveAs(path, false, false, false, false);
   w16.forceClose();
   tmp.forceClose();
   return path;
};

AF.saveAs = function (window, path, bits) {
   if (!bits || bits == 32 || /\.xisf$/i.test(path)) {
      if (!window.saveAs(path, false, false, false, false)) throw new Error("save failed: " + path);
      return path;
   }
   var img = window.mainView.image;
   var t = new ImageWindow(img.width, img.height, img.numberOfChannels, bits, false, img.isColor, "af_export");
   t.mainView.beginProcess(UndoFlag_NoSwapFile);
   t.mainView.image.assign(img);
   t.mainView.endProcess();
   t.keywords = window.keywords;
   var ok = t.saveAs(path, false, false, false, false, bits == 8 ? "quality 95" : "");
   t.forceClose();
   if (!ok) throw new Error("save failed: " + path);
   return path;
};

// ---------------------------------------------------------------------------
// Background search (same idea as SetiAstro FindBackground: darkest, flattest star-free box)
// ---------------------------------------------------------------------------

AF.findBackground = function (view, box, margin) {
   var img = view.image;
   box = box || Math.max(48, Math.round(Math.min(img.width, img.height) / 40));
   margin = margin == undefined ? 0.06 : margin;
   var x0 = Math.round(img.width * margin), y0 = Math.round(img.height * margin);
   var x1 = img.width - x0 - box, y1 = img.height - y0 - box;
   var step = Math.round(box * 0.75);
   var cands = [];
   for (var y = y0; y <= y1; y += step) {
      for (var x = x0; x <= x1; x += step) {
         var r = new Rect(x, y, x + box, y + box);
         var lum = 0, maxv = 0, mad = 0;
         for (var c = 0; c < img.numberOfChannels; ++c) {
            img.resetSelections(); img.selectedChannel = c; img.selectedRect = r;
            var med = img.median();
            lum += med; mad += img.MAD(med); maxv = Math.max(maxv, img.maximum() - med);
         }
         lum /= img.numberOfChannels; mad /= img.numberOfChannels;
         cands.push({ x: x, y: y, lum: lum, mad: mad, peak: maxv });
      }
   }
   img.resetSelections();
   if (cands.length == 0) return null;
   // reject boxes with stars (bright peaks) and the noisiest half, then take a low-percentile brightness box
   var mads = cands.map(function (c) { return c.mad; }).sort(function (a, b) { return a - b; });
   var madLimit = mads[Math.floor(mads.length * 0.5)];
   var peaks = cands.map(function (c) { return c.peak; }).sort(function (a, b) { return a - b; });
   var peakLimit = peaks[Math.floor(peaks.length * 0.4)];
   var ok = cands.filter(function (c) { return c.mad <= madLimit && c.peak <= peakLimit; });
   if (ok.length < 3) ok = cands.slice();
   ok.sort(function (a, b) { return a.lum - b.lum; });
   // 5th percentile instead of the absolute darkest: avoids dark-nebula cores and edge artefacts
   var pick = ok[Math.min(ok.length - 1, Math.floor(ok.length * 0.05))];
   return { x0: pick.x, y0: pick.y, x1: pick.x + box, y1: pick.y + box, lum: AF.round(pick.lum, 7), mad: AF.round(pick.mad, 7),
            candidates: cands.length };
};

// ---------------------------------------------------------------------------
// EZ Soft Stretch (port of EZ_SoftStretch.js v0.11.3 by Elveteek / EZ Processing Suite)
// ---------------------------------------------------------------------------

AF.findMidtonesBalance = function (v0, v1, eps) {
   eps = Math.max(1.0e-10, eps || 1.0e-8);
   var m0, m1;
   if (v1 < v0) { m0 = 0; m1 = 0.5; } else { m0 = 0.5; m1 = 1; }
   for (var it = 0; it < 200; ++it) {
      var m = 0.5 * (m0 + m1);
      var v = Math.mtf(m, v1);
      if (Math.abs(v - v0) < eps) return m;
      if (v < v0) m1 = m; else m0 = m;
   }
   return 0.5 * (m0 + m1);
};

AF.ezSoftStretch = function (view, targetMedian, expandLow, aggressiveness, zeroInWhitePoint) {
   targetMedian = targetMedian == undefined ? 0.25 : targetMedian;
   expandLow = expandLow == undefined ? 0.05 : expandLow;
   aggressiveness = aggressiveness == undefined ? 5 : aggressiveness;
   var H16 = view.computeOrFetchProperty("Histogram16");
   var rows = H16.rows, cols = H16.cols;
   var total = 0;
   for (var i = 0; i < cols; ++i) total += H16.at(0, i);
   var medV = view.computeOrFetchProperty("Median");
   var medNorm = [medV.at(0), rows == 3 ? medV.at(1) : medV.at(0), rows == 3 ? medV.at(2) : medV.at(0)];
   var medADU = [parseInt(medNorm[0] * 65536), parseInt(medNorm[1] * 65536), parseInt(medNorm[2] * 65536)];
   var black = [0, 0, 0], white = [0, 0, 0];
   for (var ch = 0; ch < rows; ++ch) {
      for (var k = cols - 1; k > 0; --k) if (H16.at(ch, k) != 0) { white[ch] = k; break; }
      var cum = [], peakX = 0, peakV = 0;
      for (var j = 0; j < medADU[ch]; ++j) {
         var avg = 0.5 * (H16.at(ch, j) + H16.at(ch, j + 1));
         cum.push((cum.length ? cum[cum.length - 1] : 0) + avg);
         if (avg > peakV) { peakX = medADU[ch]; peakV = avg; }
      }
      var madMin = 0;
      for (var q = 0; q < cum.length; ++q) if (cum[q] > (total / 10000) * aggressiveness) { madMin = q; break; }
      var n = peakX - madMin, sx = 0, sy = 0, sxy = 0, sx2 = 0;
      for (var t = madMin; t < peakX; ++t) { sx += t; sy += cum[t]; sxy += t * cum[t]; sx2 += t * t; }
      var m = (n * sxy - sx * sy) / (n * sx2 - sx * sx);
      var c0 = (sy - m * sx) / n;
      black[ch] = (n > 1 && m > 0) ? parseInt(-(c0 / m)) : 0;
   }
   if (rows == 1) { white[1] = white[2] = white[0]; black[1] = black[2] = black[0]; medNorm[1] = medNorm[2] = medNorm[0]; }
   if (!zeroInWhitePoint) white = [cols - 1, cols - 1, cols - 1];
   var medianNorm = Math.min(medNorm[0], medNorm[1], medNorm[2]);
   var whiteNorm = Math.max(white[0], white[1], white[2]) / (cols - 1);
   var blackNorm = Math.max(0, Math.min(black[0], black[1], black[2])) / (cols - 1);
   if (!(blackNorm > 0) || medianNorm < blackNorm) blackNorm = 0;
   var newTarget = targetMedian * whiteNorm - expandLow * whiteNorm;
   var mtf = 1 - AF.findMidtonesBalance(medianNorm - blackNorm, newTarget, 1.0e-8);
   var HT = new HistogramTransformation;
   HT.H = [[0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1],
           [blackNorm, mtf, whiteNorm, -expandLow, 1.0], [0, 0.5, 1, 0, 1]];
   HT.executeOn(view, false);
   return { blackPoint: AF.round(blackNorm, 8), midtones: AF.round(mtf, 8), whitePoint: whiteNorm,
            medianBefore: AF.round(medianNorm, 8), targetMedian: targetMedian, expandLow: expandLow };
};

// Lowest value that clips `fraction` of the darkest pixels (luminance-ish: min over channels), via Histogram16.
AF.shadowsForClipFraction = function (view, fraction) {
   var H16 = view.computeOrFetchProperty("Histogram16");
   var rows = H16.rows, cols = H16.cols, best = 1;
   for (var ch = 0; ch < rows; ++ch) {
      var total = 0;
      for (var i = 0; i < cols; ++i) total += H16.at(ch, i);
      var acc = 0, k = 0;
      for (; k < cols; ++k) { acc += H16.at(ch, k); if (acc > total * fraction) break; }
      best = Math.min(best, k / (cols - 1));
   }
   return best;
};
