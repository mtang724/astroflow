// astroflow processing steps. Each step is STEPS[op](ctx, p) -> info object (JSON-serialisable).
// ctx.win.<name> holds ImageWindows ("main", and "stars" after star removal); p.target picks one (default "main").
// Defaults follow knowledge/videos/ep1-osc-broadband-nebula.md (PixInsight 进阶教程 第1期) unless noted.

var STEPS = {};

// p.target: a window name, or a list of them (the first one open is used: ["L", "main"] = L if there is one)
function afWin(ctx, p) {
   var names = [].concat((p && p.target) || "main");
   for (var i = 0; i < names.length; ++i) if (ctx.win[names[i]]) return ctx.win[names[i]];
   throw new Error("No window named '" + names.join("' or '") + "' (have: " + Object.keys(ctx.win).join(",") + ")");
}

function afApply(P, params) {
   if (params == undefined || params == null) return;
   for (var k in params) {
      if (!(k in P)) throw new Error(P.constructor.name + " has no parameter '" + k + "'");
      P[k] = params[k];
   }
}

function afRect(r) { return new Rect(r.x0, r.y0, r.x1, r.y1); }

// Masks: "lum" (CIE L*, shadows clipped), "range" (RangeSelection, video ep2: low 0.16, smoothness 65),
// "object" (soft ellipse around the catalogued object, needs locate_object), "color" (one hue of a narrowband palette:
// maskColor red|yellow|green|cyan|blue|magenta, maskBlur sigma, videos ep4/ep5); prefix "inverse_" to invert.
function afWithMask(ctx, w, p, fn) {
   var mask = null;
   if (p.mask) {
      var kind = String(p.mask).replace(/^inverse_/, "");
      if (kind == "lum") mask = AF.lumMask(w.mainView, p.maskClip == undefined ? 0.10 : p.maskClip, p.maskMidtones || 0.5);
      else if (kind == "range") mask = AF.rangeMask(w.mainView, p.rangeLow == undefined ? 0.16 : p.rangeLow,
                                                     p.rangeHigh || 1.0, p.rangeFuzziness || 0, p.rangeSmoothness || 65);
      else if (kind == "object") mask = AF.objectMask(ctx, w.mainView, p.objectScale || 1.2, p.feather || 0.35);
      else if (kind == "color") mask = AF.colorMask(w.mainView, p.maskColor || "blue", p.maskBlur == undefined ? 15 : p.maskBlur);
      else throw new Error("unknown mask " + p.mask);
      w.setMask(mask, /^inverse_/.test(String(p.mask)));
      w.maskEnabled = true;
   }
   try { return fn(); }
   finally {
      if (mask) { w.removeMask(); mask.forceClose(); }
   }
}

AF.rangeMask = function (view, low, high, fuzziness, smoothness) {
   var before = AF.windowIds();
   var RS = new RangeSelection;
   RS.lowRange = low; RS.highRange = high; RS.fuzziness = fuzziness; RS.smoothness = smoothness;
   RS.screening = false; RS.toLightness = true; RS.invert = false;
   RS.executeOn(view, false);
   var nws = AF.newWindows(before);
   if (nws.length == 0) throw new Error("RangeSelection produced no mask");
   for (var i = 1; i < nws.length; ++i) nws[i].forceClose();
   nws[0].hide();
   return nws[0];
};

// One hue of the image: CIE chroma where the CIE hue (PixelMath's CIEh, 0..1) is within 1/6 of the colour's hue, falling
// off linearly to 0 there, rescaled to 0..1 and blurred so curves through it leave no edges. In HOO the OIII is cyan to
// blue, in SHO the SII+Ha mix is yellow to orange.
AF.HUES = { red: 0, yellow: 1 / 6, green: 1 / 3, cyan: 1 / 2, blue: 2 / 3, magenta: 5 / 6 };
AF.colorMask = function (view, color, blur) {
   var hue = AF.HUES[color];
   if (hue == undefined) throw new Error("unknown mask colour " + color + " (" + Object.keys(AF.HUES).join(", ") + ")");
   var d = "abs(CIEh($T) - " + hue + ")";
   var PM = new PixelMath;
   PM.expression = "max(0, 1 - 6*min(" + d + ", 1 - " + d + ")) * CIEc($T)";
   PM.useSingleExpression = true; PM.createNewImage = true; PM.showNewImage = false; PM.newImageId = "af_color_mask";
   PM.newImageColorSpace = PixelMath.prototype.Gray; PM.newImageSampleFormat = PixelMath.prototype.f32;
   PM.rescale = true; PM.truncate = true;
   PM.executeOn(view, false);
   var m = AF.windowById("af_color_mask");
   if (blur > 0) {
      var B = new PixelMath;
      B.expression = "gconv($T, " + blur + ", 1, 0)";
      B.useSingleExpression = true; B.createNewImage = false; B.rescale = false; B.truncate = true;
      B.executeOn(m.mainView, false);
   }
   m.hide();
   return m;
};

// Soft-edged ellipse (scale x catalogue size, linear fall-off over `feather` x semi-axes).
AF.objectMask = function (ctx, view, scale, feather) {
   var o = ctx.object;
   if (!o) throw new Error("object mask needs locate_object first");
   var a = o.a * scale, b = o.b * scale, c = Math.cos(o.angle), s = Math.sin(o.angle);
   var PM = new PixelMath;
   PM.expression = "u=((x()-" + o.cx + ")*" + c + "+(y()-" + o.cy + ")*" + s + ")/" + a + ";" +
                   "v=(-(x()-" + o.cx + ")*" + s + "+(y()-" + o.cy + ")*" + c + ")/" + b + ";" +
                   "r=sqrt(u*u+v*v);" +
                   "iif(r<1,1,max(0,1-(r-1)/" + feather + "))";
   PM.symbols = "u, v, r";
   PM.useSingleExpression = true; PM.createNewImage = true; PM.showNewImage = false;
   PM.newImageId = "af_objmask"; PM.newImageColorSpace = PixelMath.prototype.Gray;
   PM.newImageSampleFormat = PixelMath.prototype.f32;
   PM.executeOn(view, false);
   var m = AF.windowById("af_objmask");
   m.hide();
   return m;
};

// Luminance mask: CIE L* of the view, shadows clipped so noise in the background is protected.
AF.lumMask = function (view, clip, midtones) {
   var PM = new PixelMath;
   PM.expression = "CIEL($T)";
   PM.useSingleExpression = true;
   PM.createNewImage = true;
   PM.showNewImage = false;
   PM.newImageId = "af_lmask";
   PM.newImageColorSpace = PixelMath.prototype.Gray;
   PM.newImageSampleFormat = PixelMath.prototype.f32;
   if (view.image.isColor) PM.executeOn(view, false);
   else { PM.expression = "$T"; PM.executeOn(view, false); }
   var m = AF.windowById("af_lmask");
   m.hide();
   AF.applyHT(m.mainView, [clip], [midtones]);
   return m;
};

// ---------------------------------------------------------------- geometry

STEPS.crop = function (ctx, p) {
   var w = afWin(ctx, p), img = w.mainView.image;
   var W = img.width, H = img.height;
   var l, r, t, b;
   if (p.rect) {
      var R = (p.rect instanceof Array) ? { x0: p.rect[0], y0: p.rect[1], x1: p.rect[2], y1: p.rect[3] } : p.rect;
      var ok = [R.x0, R.y0, R.x1, R.y1].every(function (v) { return typeof v == "number" && isFinite(v); });
      if (!ok || R.x0 < 0 || R.y0 < 0 || R.x1 > W || R.y1 > H || R.x1 - R.x0 < 16 || R.y1 - R.y0 < 16)
         throw new Error("crop rect must be {x0,y0,x1,y1} or [x0,y0,x1,y1] inside " + W + "x" + H + ", got " + JSON.stringify(p.rect));
      l = Math.round(R.x0); t = Math.round(R.y0); r = W - Math.round(R.x1); b = H - Math.round(R.y1);
   }
   else { var px = p.pixels != undefined ? p.pixels : Math.round(Math.min(W, H) * (p.fraction || 0.01)); l = r = t = b = px; }
   var C = new DynamicCrop;
   C.refWidth = W; C.refHeight = H;
   C.outWidth = W - l - r; C.outHeight = H - t - b;
   C.width = (W - l - r) / W; C.height = (H - t - b) / H;
   C.centerX = (l + (W - l - r) / 2) / W; C.centerY = (t + (H - t - b) / 2) / H;
   C.angle = 0;
   C.noGUIMessages = true;   // otherwise a confirmation box (astrometric solution will be deleted) blocks headless runs
   C.executeOn(w.mainView, false);
   return { from: [W, H], to: [w.mainView.image.width, w.mainView.image.height] };
};

// ---------------------------------------------------------------- background / gradients

STEPS.find_background = function (ctx, p) {
   var w = afWin(ctx, p);
   var r = p.rect ? p.rect : AF.findBackground(w.mainView, p.box, p.margin);
   if (!r) throw new Error("background search failed");
   ctx.bgRect = r;
   r.stats = AF.stats(w.mainView, afRect(r));
   return r;
};

STEPS.gradient_correction = function (ctx, p) {
   var w = afWin(ctx, p);
   var G = new GradientCorrection;
   afApply(G, p.hasOwnProperty("params") ? p.params : null);
   G.generateGradientModel = !!p.saveModel;
   var before = AF.windowIds();
   var st0 = AF.stats(w.mainView);
   G.executeOn(w.mainView, false);
   var info = { before: st0.median, after: AF.stats(w.mainView).median };
   var nws = AF.newWindows(before);
   for (var i = 0; i < nws.length; ++i) {
      var mv = nws[i].mainView;
      var ms = AF.stats(mv);
      info.model = { id: mv.id, median: ms.median, min: ms.min, max: ms.max };
      if (p.saveModel) info.model.preview = AF.savePreview(mv, p.saveModel, 1200, true, false);   // unlinked: shows the gradient shape per channel
      nws[i].forceClose();
   }
   return info;
};

STEPS.abe = function (ctx, p) {
   var w = afWin(ctx, p);
   var A = new AutomaticBackgroundExtractor;
   A.polyDegree = 2; A.targetCorrection = 1; /* Subtract */ A.normalize = true; A.replaceTarget = true; A.discardModel = true;
   afApply(A, p.hasOwnProperty("params") ? p.params : null);
   A.executeOn(w.mainView, false);
   return { after: AF.stats(w.mainView).median };
};

// ---------------------------------------------------------------- astrometry & colour

STEPS.plate_solve = function (ctx, p) {
   var w = afWin(ctx, p);
   if (w.hasAstrometricSolution && !p.force)
      return { solved: true, already: true, summary: w.astrometricSolutionSummary() };
   var solver = new ImageSolver();
   solver.Init(w, false);
   var cfg = solver.solverCfg;
   cfg.useActive = true; cfg.files = [];
   cfg.catalogMode = CatalogMode.prototype.Automatic;
   cfg.vizierServer = "https://vizier.cds.unistra.fr/";
   cfg.magnitude = 12; cfg.autoMagnitude = true; cfg.maxIterations = 100;
   cfg.structureLayers = 5; cfg.minStructureSize = 0; cfg.hotPixelFilterRadius = 1; cfg.noiseReductionFilterRadius = 0;
   cfg.sensitivity = 0.5; cfg.peakResponse = 0.5; cfg.brightThreshold = 3.0; cfg.maxStarDistortion = 0.6;
   cfg.autoPSF = false; cfg.generateErrorImg = false; cfg.showStars = false; cfg.catalog = "PPMXL";
   cfg.showStarMatches = false; cfg.showSimplifiedSurfaces = false; cfg.showDistortion = false;
   cfg.distortionCorrection = true; cfg.rbfType = WCS_DEFAULT_RBF_TYPE; cfg.maxSplinePoints = WCS_DEFAULT_MAX_SPLINE_POINTS;
   cfg.splineOrder = 2; cfg.splineSmoothing = 0.005; cfg.enableSimplifier = true; cfg.simplifierRejectFraction = 0.10;
   cfg.outlierDetectionRadius = 160; cfg.outlierDetectionMinThreshold = 4.0; cfg.outlierDetectionSigma = 5.0;
   cfg.generateDistortModel = false; cfg.outSuffix = "_ast"; cfg.projection = 0; cfg.projectionOriginMode = 0;
   cfg.restrictToHQStars = false; cfg.intersectionMode = IntersectionMode.prototype.Automatic;
   cfg.tryApparentCoordinates = true; cfg.tryExhaustiveInitialAlignment = false;
   var md = solver.metadata;
   if (p.ra != undefined) md.ra = p.ra;
   if (p.dec != undefined) md.dec = p.dec;
   if (p.focal != undefined) { md.focal = p.focal; md.useFocal = true; }
   if (p.pixelSize != undefined) md.xpixsz = p.pixelSize;
   if (p.epoch != undefined) md.epoch = p.epoch;
   if (md.focal > 0 && md.xpixsz > 0) md.resolution = md.xpixsz / md.focal * 0.18 / Math.PI;
   var ok = solver.SolveImage(w);
   return { solved: !!ok, summary: ok ? w.astrometricSolutionSummary() : null,
            hint: { ra: md.ra, dec: md.dec, focal: md.focal, pixelSize: md.xpixsz } };
};

STEPS.spcc = function (ctx, p) {
   var w = afWin(ctx, p);
   if (!w.hasAstrometricSolution) throw new Error("SPCC needs an astrometric solution: run plate_solve first");
   var S = new SpectrophotometricColorCalibration;   // defaults = video: Average Spiral Galaxy, Sony Color Sensor R/G/B-UVIRcut, Ideal QE, Gaia DR3/SP
   S.generateGraphs = false; S.generateStarMaps = false; S.generateTextFiles = false;
   if (ctx.bgRect && p.useBackgroundROI != false) {
      var r = ctx.bgRect;
      S.backgroundUseROI = true; S.backgroundROIX0 = r.x0; S.backgroundROIY0 = r.y0; S.backgroundROIX1 = r.x1; S.backgroundROIY1 = r.y1;
   }
   if (p.narrowband) {
      // narrowband palettes (video ep4): no filter curves, the lines' wavelengths and the filters' bandwidth instead
      var bw = p.bandwidth || 7, lines = { HOO: [656.3, 500.7, 500.7], SHO: [671.6, 656.3, 500.7] }[p.narrowband];
      if (!lines) throw new Error("unknown narrowband palette " + p.narrowband);
      S.narrowbandMode = true; S.narrowbandOptimizeStars = false;
      S.redFilterWavelength = lines[0]; S.greenFilterWavelength = lines[1]; S.blueFilterWavelength = lines[2];
      S.redFilterBandwidth = S.greenFilterBandwidth = S.blueFilterBandwidth = bw;
   }
   afApply(S, p.hasOwnProperty("params") ? p.params : null);
   var before = AF.windowIds();
   var st0 = AF.stats(w.mainView);
   var ok = S.executeOn(w.mainView, false);
   var nws = AF.newWindows(before);
   for (var i = 0; i < nws.length; ++i) nws[i].forceClose();
   if (!ok) throw new Error("SPCC failed");
   var st1 = AF.stats(w.mainView);
   ctx.colorCalibrated = true;
   return { medianBefore: st0.median, medianAfter: st1.median,
            bgAfter: ctx.bgRect ? AF.stats(w.mainView, afRect(ctx.bgRect)).median : null };
};

// Manual colour calibration (video's "BNCC"): BackgroundNeutralization + ColorCalibration on a background box.
STEPS.bncc = function (ctx, p) {
   var w = afWin(ctx, p);
   if (!ctx.bgRect) STEPS.find_background(ctx, {});
   var r = ctx.bgRect, R = afRect(r);
   var st = AF.stats(w.mainView, R);
   var hi = 0;
   for (var c = 0; c < st.channels; ++c) hi = Math.max(hi, st.median[c] + 4 * 1.4826 * st.mad[c]);
   var BN = new BackgroundNeutralization;
   BN.useROI = true; BN.roiX0 = r.x0; BN.roiY0 = r.y0; BN.roiX1 = r.x1; BN.roiY1 = r.y1;
   BN.backgroundLow = 0; BN.backgroundHigh = p.bnHigh || hi;
   BN.mode = 2; /* RescaleAsNeeded */ BN.targetBackground = 0.001;
   BN.executeOn(w.mainView, false);
   var st2 = AF.stats(w.mainView, R);
   var bgHi = 0;
   for (c = 0; c < st2.channels; ++c) bgHi = Math.max(bgHi, st2.median[c] + 4 * 1.4826 * st2.mad[c]);
   var noise = AF.noise(w.mainView);
   var CC = new ColorCalibration;
   CC.whiteReferenceViewId = ""; CC.whiteUseROI = false;
   CC.whiteLow = p.whiteLow || Math.max(0.005, st2.median[1] + 20 * noise[1]);
   CC.whiteHigh = 0.9; CC.structureDetection = p.structureDetection != false; CC.structureLayers = 5; CC.noiseLayers = 1;
   var o = ctx.object, img = w.mainView.image, box = null;
   if (p.whiteROI == "object" && o) {
      // galaxies (video ep2): white reference = a box on the object's body, structure detection OFF
      var hw = Math.max(32, o.a * (p.whiteScale || 0.6)), hh = Math.max(32, Math.max(o.b, o.a * 0.35) * (p.whiteScale || 0.6));
      box = [o.cx - hw, o.cy - hh, o.cx + hw, o.cy + hh];
   } else if (p.whiteROI == "bright" || (p.whiteROI == "object" && p.whiteFallback == "bright")) {
      // SHO (video ep5): white reference = the bright nebula core, found without astrometry: the brightest cell of a
      // 5 x 4 grid (by median, so stars do not count)
      var gw = img.width / 5, gh = img.height / 4, best = -1;
      for (var gy = 0; gy < 4; ++gy) for (var gx = 0; gx < 5; ++gx) {
         var cell = new Rect(Math.round(gx * gw), Math.round(gy * gh), Math.round((gx + 1) * gw), Math.round((gy + 1) * gh));
         var m = AF.stats(w.mainView, cell).median, lum = 0;
         for (c = 0; c < m.length; ++c) lum += m[c] / m.length;
         if (lum > best) { best = lum; box = [cell.x0, cell.y0, cell.x1, cell.y1]; }
      }
   } else if (p.whiteROI == "object") AF.log("bncc: object not located (no astrometric solution): white reference = whole image");
   if (box) {
      CC.whiteUseROI = true;
      CC.whiteROIX0 = Math.max(0, Math.round(box[0])); CC.whiteROIY0 = Math.max(0, Math.round(box[1]));
      CC.whiteROIX1 = Math.min(img.width, Math.round(box[2])); CC.whiteROIY1 = Math.min(img.height, Math.round(box[3]));
      CC.whiteLow = p.whiteLow || 0; CC.structureDetection = p.structureDetection == true;
   }
   CC.backgroundUseROI = true; CC.backgroundROIX0 = r.x0; CC.backgroundROIY0 = r.y0; CC.backgroundROIX1 = r.x1; CC.backgroundROIY1 = r.y1;
   CC.backgroundLow = 0; CC.backgroundHigh = p.ccBackgroundHigh || bgHi;
   CC.executeOn(w.mainView, false);
   ctx.colorCalibrated = true;
   return { bnHigh: BN.backgroundHigh, whiteLow: CC.whiteLow, ccBackgroundHigh: CC.backgroundHigh,
            whiteROI: CC.whiteUseROI ? [CC.whiteROIX0, CC.whiteROIY0, CC.whiteROIX1, CC.whiteROIY1] : null,
            structureDetection: CC.structureDetection, bgAfter: AF.stats(w.mainView, R).median };
};

// SPCC when the image is (or can be) plate-solved, otherwise the manual BN+CC route (video: prefer SPCC).
// p.narrowband ("HOO") + p.bandwidth (nm): SPCC in narrowband mode. p.target reaches the steps it calls.
STEPS.color_calibration = function (ctx, p) {
   var w = afWin(ctx, p);
   var errors = [];
   function sub(q, extra) {
      var o = {};
      for (var k in (q || {})) o[k] = q[k];
      for (k in (extra || {})) if (extra[k] != undefined) o[k] = extra[k];
      if (p.target) o.target = p.target;
      return o;
   }
   if (p.method != "bncc") {
      try {
         if (!w.hasAstrometricSolution) {
            var ps = STEPS.plate_solve(ctx, sub(p.solve));
            if (!ps.solved) throw new Error("plate solve failed");
         }
         var r = STEPS.spcc(ctx, sub(p.spcc, { narrowband: p.narrowband, bandwidth: p.bandwidth }));
         r.method = "spcc";
         return r;
      } catch (e) {
         errors.push("spcc: " + e);
         AF.log("SPCC route failed, falling back to BN+CC: " + e);
      }
   }
   var b = STEPS.bncc(ctx, sub(p.bncc));
   b.method = "bncc";
   b.errors = errors;
   return b;
};

// ---------------------------------------------------------------- RC Astro tools

STEPS.bxt = function (ctx, p) {
   var w = afWin(ctx, p);
   var B = new BlurXTerminator;     // video: defaults (sharpen_stars 0.5, adjust_halos 0, auto PSF, sharpen_nonstellar 0.5)
   afApply(B, p.hasOwnProperty("params") ? p.params : null);
   if (!B.executeOn(w.mainView, false)) throw new Error("BlurXTerminator did not run (see console.txt)");
   return { params: p.hasOwnProperty("params") ? p.params : "defaults" };
};

STEPS.nxt = function (ctx, p) {
   var w = afWin(ctx, p);
   var N = new NoiseXTerminator;    // AI3; linear video values: intensity 0.30, colour 0.40; nonlinear: 0.65 / 0.90
   N.enable_color_separation = true;
   N.denoise = 0.30; N.denoise_color = 0.40; N.iterations = 2;
   afApply(N, p.hasOwnProperty("params") ? p.params : null);
   var n0 = AF.noise(w.mainView);
   if (!N.executeOn(w.mainView, false)) throw new Error("NoiseXTerminator did not run (see console.txt)");
   return { noiseBefore: n0, noiseAfter: AF.noise(w.mainView), denoise: N.denoise, denoise_color: N.denoise_color };
};

// p.perChannel: each colour channel on its own (video ep4: on the whole HOO image SXT took red nebula for stars).
STEPS.sxt = function (ctx, p) {
   var w = afWin(ctx, p);
   var S = new StarXTerminator;
   S.stars = true; S.unscreen = p.unscreen != false; S.overlap = p.largeOverlap ? 0.5 : 0.2;
   afApply(S, p.hasOwnProperty("params") ? p.params : null);
   if (p.perChannel && w.mainView.image.isColor) return afSxtChannels(ctx, w, S);
   var before = AF.windowIds();
   if (!S.executeOn(w.mainView, false)) throw new Error("StarXTerminator did not run (see console.txt)");
   var nws = AF.newWindows(before), starsWin = null;
   for (var i = 0; i < nws.length; ++i) {
      if (!starsWin && /star/i.test(nws[i].mainView.id)) starsWin = nws[i];
      else nws[i].forceClose();
   }
   if (!starsWin) throw new Error("StarXTerminator produced no star image");
   if (ctx.win.stars) ctx.win.stars.forceClose();
   starsWin.mainView.id = "stars";
   starsWin.hide();
   ctx.win.stars = starsWin;
   ctx.unscreen = S.unscreen;
   return { starsId: "stars", unscreen: S.unscreen };
};

function afSxtChannels(ctx, w, S) {
   var CE = new ChannelExtraction;
   CE.colorSpace = ChannelExtraction.prototype.RGB; CE.sampleFormat = ChannelExtraction.prototype.SameAsSource;
   CE.channels = [[true, "af_c0"], [true, "af_c1"], [true, "af_c2"]];
   CE.executeOn(w.mainView, false);
   for (var c = 0; c < 3; ++c) {
      var cw = AF.windowById("af_c" + c), before = AF.windowIds();
      cw.hide();
      if (!S.executeOn(cw.mainView, false)) throw new Error("StarXTerminator did not run on channel " + c);
      var nws = AF.newWindows(before);
      if (!nws.length) throw new Error("StarXTerminator produced no star image for channel " + c);
      nws[0].mainView.id = "af_s" + c;
      nws[0].hide();
      for (var i = 1; i < nws.length; ++i) nws[i].forceClose();
   }
   function merge(prefix, target, id) {
      var PM = new PixelMath;
      PM.expression = prefix + "0"; PM.expression1 = prefix + "1"; PM.expression2 = prefix + "2";
      PM.useSingleExpression = false; PM.rescale = false; PM.truncate = true;
      PM.createNewImage = !!id; PM.showNewImage = false;
      if (id) { PM.newImageId = id; PM.newImageColorSpace = PixelMath.prototype.RGB; PM.newImageSampleFormat = PixelMath.prototype.f32; }
      PM.executeOn(target, false);
   }
   merge("af_c", w.mainView, null);
   if (ctx.win.stars) ctx.win.stars.forceClose();
   merge("af_s", w.mainView, "af_stars");
   for (c = 0; c < 3; ++c) { AF.windowById("af_c" + c).forceClose(); AF.windowById("af_s" + c).forceClose(); }
   var sw = AF.windowById("af_stars");
   sw.mainView.id = "stars";
   sw.hide();
   ctx.win.stars = sw;
   ctx.unscreen = S.unscreen;
   return { starsId: "stars", unscreen: S.unscreen, perChannel: true };
}

// Natural star colours from narrowband stars (videos ep5): a star's light spans the spectrum, so R takes Ha (with SII),
// G mixes Ha and OIII, B is OIII; then green is removed. palette: the star image's channels, "SHO" (R = SII, G = Ha,
// B = OIII) or "HOO" (R = Ha, G = B = OIII).
STEPS.nb_star_colors = function (ctx, p) {
   var w = afWin(ctx, { target: p.target || "stars" });
   var e = (p.palette || "SHO") == "HOO" ? ["$T[0]", "0.3*$T[0] + 0.7*$T[1]", "$T[2]"]
                                         : ["0.5*$T[1] + 0.5*$T[0]", "0.3*$T[1] + 0.7*$T[2]", "$T[2]"];
   var PM = new PixelMath;
   PM.expression = e[0]; PM.expression1 = e[1]; PM.expression2 = e[2];
   PM.useSingleExpression = false; PM.createNewImage = false; PM.rescale = false; PM.truncate = true;
   PM.executeOn(w.mainView, false);
   var N = new SCNR;
   N.colorToRemove = 1; N.protectionMethod = 2; N.amount = p.scnr == undefined ? 1.0 : p.scnr; N.preserveLightness = true;
   N.executeOn(w.mainView, false);
   return { palette: p.palette || "SHO", expressions: e };
};

// Another window takes p.target's place, when there is one (video ep4: RGB stars replace the narrowband stars).
STEPS.use_window = function (ctx, p) {
   var name = p.target || "main", src = ctx.win[p.from];
   if (!src) return { used: false };
   if (ctx.win[name]) ctx.win[name].forceClose();
   delete ctx.win[p.from];
   src.mainView.id = name;
   ctx.win[name] = src;
   return { used: true, from: p.from };
};

// ---------------------------------------------------------------- stretching

// p.matchLightnessOf: a stretched colour window whose lightness (CIE L*) median, times p.matchScale (default 1),
// becomes the target median, so an L channel put in with LRGBCombination keeps the image's brightness (video ep3
// matched them by eye).
STEPS.stretch = function (ctx, p) {
   var w = afWin(ctx, p);
   var method = p.method || "ez_soft";
   var info = { method: method };
   if (p.matchLightnessOf) {
      var PM = new PixelMath;
      PM.expression = "CIEL($T)";
      PM.useSingleExpression = true; PM.createNewImage = true; PM.showNewImage = false; PM.newImageId = "af_lightness";
      PM.newImageColorSpace = PixelMath.prototype.Gray; PM.newImageSampleFormat = PixelMath.prototype.f32;
      PM.executeOn(afWin(ctx, { target: p.matchLightnessOf }).mainView, false);
      var lw = AF.windowById("af_lightness");
      p.targetMedian = AF.round(lw.mainView.image.median() * (p.matchScale || 1), 4);
      lw.forceClose();
      info.matchedTo = p.matchLightnessOf;
   }
   if (method == "ez_soft") {
      var r = AF.ezSoftStretch(w.mainView, p.targetMedian == undefined ? 0.20 : p.targetMedian,
                               p.expandLow == undefined ? 0.05 : p.expandLow, p.aggressiveness || 5, !!p.zeroInWhitePoint);
      for (var k in r) info[k] = r[k];
   } else if (method == "stf") {
      var s = AF.autoSTF(w.mainView, p.linked != false, p.targetMedian || 0.25, p.shadowsClip || -2.8);
      AF.applyHT(w.mainView, s.c0, s.m);
      info.c0 = s.c0; info.m = s.m;
   } else if (method == "mas") {
      var M = new MultiscaleAdaptiveStretch;
      afApply(M, p.hasOwnProperty("params") ? p.params : null);
      M.executeOn(w.mainView, false);
   } else throw new Error("unknown stretch method " + method);
   // the very same transformation on other windows (e.g. a composite whose stars are split off afterwards)
   var also = p.alsoOn || [];
   for (var i = 0; i < also.length; ++i) {
      var ow = ctx.win[also[i]];
      if (!ow) throw new Error("stretch.alsoOn: no window '" + also[i] + "'");
      if (method == "ez_soft") {
         var HT = new HistogramTransformation;
         HT.H = [[0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1],
                 [info.blackPoint, info.midtones, info.whitePoint, -info.expandLow, 1.0], [0, 0.5, 1, 0, 1]];
         HT.executeOn(ow.mainView, false);
      } else if (method == "stf") AF.applyHT(ow.mainView, info.c0, info.m);
      else throw new Error("stretch.alsoOn needs method ez_soft or stf");
   }
   ctx.linear = false;
   info.medianAfter = AF.stats(w.mainView).median;
   return info;
};

// Stars from a stretched composite and its stretched starless version (same stretch): the inverse of the screen
// blend, so `recombine` (screen) gives the composite back. Used instead of SXT when the layers already exist
// separately (astroflow.comet) - SXT would also take a comet's bright coma for a star.
STEPS.split_stars = function (ctx, p) {
   var w = afWin(ctx, p);
   var comp = ctx.win[p.composite];
   if (!comp) throw new Error("split_stars: no composite window '" + p.composite + "'");
   var PM = new PixelMath;
   PM.expression = "1 - (1 - $T)/max(1 - " + w.mainView.id + ", 0.000001)";
   PM.useSingleExpression = true; PM.createNewImage = false; PM.rescale = false; PM.truncate = true;
   PM.executeOn(comp.mainView, false);
   if (ctx.win.stars) ctx.win.stars.forceClose();
   delete ctx.win[p.composite];
   comp.mainView.id = "stars";
   ctx.win.stars = comp;
   ctx.unscreen = true;
   return { starsId: "stars", from: p.composite };
};

// shadows: a number, "auto" (clip p.clipFraction of the darkest pixels, capped at maxShadows) or "sky" (the black
// point that leaves the sky median at p.skyTarget; use it on registered stacks, whose empty borders make the
// clip-fraction rule clip almost nothing).
STEPS.ht = function (ctx, p) {
   var w = afWin(ctx, p);
   var c0 = p.shadows, m = p.midtones || 0.5;
   if (c0 == "sky") {
      var st = AF.stats(w.mainView), med = 0;
      for (var i = 0; i < st.median.length; ++i) med += st.median[i] / st.median.length;
      var u = Math.mtf(1 - m, p.skyTarget || 0.09);         // input value that this midtones balance maps to the target
      c0 = Math.max(0, (med - u) / (1 - u));
      if (p.maxShadows) c0 = Math.min(c0, p.maxShadows);
   } else if (c0 == "none") c0 = 0;
   else {
      if (c0 == undefined || c0 == "auto") c0 = AF.shadowsForClipFraction(w.mainView, p.clipFraction || 0.0004);
      c0 = Math.min(c0, p.maxShadows || 0.08);
   }
   // channelShadows "sky": each colour channel's black point lifts that channel's sky to the darkest one, so a red or
   // yellow cast in the background goes (videos ep4/ep5 did it by hand on the R, G, B rows)
   var rows = [[0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1], [0, 0.5, 1, 0, 1]], channelShadows = null;
   if (p.channelShadows == "sky" && w.mainView.image.isColor) {
      if (!ctx.bgRect) STEPS.find_background(ctx, {});
      var sky = AF.stats(w.mainView, afRect(ctx.bgRect)).median;
      var low = Math.min(sky[0], sky[1], sky[2]);
      channelShadows = [];
      for (var k = 0; k < 3; ++k) rows[k][0] = channelShadows[k] = AF.round(Math.max(0, (sky[k] - low) / (1 - low)), 6);
   }
   var HT = new HistogramTransformation;
   HT.H = [rows[0], rows[1], rows[2], [c0, m, p.highlights || 1.0, 0, 1], [0, 0.5, 1, 0, 1]];
   HT.executeOn(w.mainView, false);
   return { shadows: AF.round(c0, 6), midtones: m, channelShadows: channelShadows, medianAfter: AF.stats(w.mainView).median };
};

// ---------------------------------------------------------------- nonlinear enhancement

STEPS.lhe = function (ctx, p) {
   var w = afWin(ctx, p);
   var L = new LocalHistogramEqualization;   // video: radius 162, contrast limit 1.3, amount 0.8, 8-bit, circular
   L.radius = 162; L.slopeLimit = 1.3; L.amount = 0.8; L.histogramBins = 0; L.circularKernel = true;
   afApply(L, p.hasOwnProperty("params") ? p.params : null);
   afWithMask(ctx, w, p, function () { L.executeOn(w.mainView, false); });
   return { radius: L.radius, slopeLimit: L.slopeLimit, amount: L.amount, mask: p.mask || null };
};

STEPS.curves = function (ctx, p) {
   var w = afWin(ctx, p);
   var C = new CurvesTransformation;
   var ch = p.channels || {};
   for (var k in ch) { C[k] = ch[k]; C[k + "t"] = CurvesTransformation.prototype.AkimaSubsplines; }
   afWithMask(ctx, w, p, function () { for (var i = 0; i < (p.passes || 1); ++i) C.executeOn(w.mainView, false); });
   return { channels: Object.keys(ch), mask: p.mask || null };
};

// Saturation boost through an L mask (video 21期 method): S curve lifted at its midpoint, optional RGB nudges.
STEPS.saturation = function (ctx, p) {
   var boost = p.boost == undefined ? 0.60 : p.boost;
   // maskMidtones < 0.5 brightens the L mask so mid-brightness nebulosity gets most of the boost (with the plain
   // 0.5 mask a 0.60 curve changed the subject chroma by only a few percent -> washed-out results)
   var q = { target: p.target, mask: p.mask == undefined ? "lum" : p.mask, maskClip: p.maskClip == undefined ? 0.10 : p.maskClip,
             maskMidtones: p.maskMidtones == undefined ? 0.3 : p.maskMidtones,
             passes: p.passes || 1, channels: { S: [[0, 0], [0.5, boost], [1, 1]] } };
   var rgb = p.rgb || {};
   for (var k in rgb) if (rgb[k]) q.channels[k] = [[0, 0], [0.5, 0.5 + rgb[k]], [1, 1]];
   var info = STEPS.curves(ctx, q);
   info.boost = boost; info.rgb = rgb;
   return info;
};

STEPS.usm = function (ctx, p) {
   var w = afWin(ctx, p);
   var U = new UnsharpMask;   // video: StdDev 2.0, amount 0.6, lightness
   U.sigma = 2.0; U.amount = 0.6; U.useLuminance = true; U.linear = false; U.deringing = false;
   afApply(U, p.hasOwnProperty("params") ? p.params : null);
   afWithMask(ctx, w, p, function () { U.executeOn(w.mainView, false); });
   return { sigma: U.sigma, amount: U.amount };
};

STEPS.scnr = function (ctx, p) {
   var w = afWin(ctx, p);
   var S = new SCNR;    // video (stars): green, Average Neutral, 0.81
   S.colorToRemove = 1; S.protectionMethod = 2; S.amount = 0.81; S.preserveLightness = true;
   afApply(S, p.hasOwnProperty("params") ? p.params : null);
   if (p.color == "magenta") {
      // invert -> remove green -> invert removes magenta casts (narrowband / multiband stars)
      var inv = new Invert;
      inv.executeOn(w.mainView, false); S.executeOn(w.mainView, false); inv.executeOn(w.mainView, false);
   } else S.executeOn(w.mainView, false);
   return { amount: S.amount, color: p.color || "green" };
};

STEPS.pixelmath = function (ctx, p) {
   var w = afWin(ctx, p);
   var PM = new PixelMath;
   PM.expression = p.expression; PM.useSingleExpression = true; PM.createNewImage = false;
   PM.rescale = !!p.rescale; PM.truncate = true;
   PM.executeOn(w.mainView, false);
   return { expression: p.expression };
};

// Put the stars back: screen blend for unscreened stars (video: ~((~starless)*(~stars))), plain add otherwise.
STEPS.recombine = function (ctx, p) {
   var w = afWin(ctx, { target: "main" });
   var s = ctx.win.stars;
   if (!s) throw new Error("no star image to recombine (run sxt first)");
   var a = w.mainView.id, b = s.mainView.id;
   var k = p.starsAmount == undefined ? 1 : p.starsAmount;
   var expr = (p.mode || (ctx.unscreen == false ? "add" : "screen")) == "add"
      ? a + " + " + k + "*" + b
      : "~((~" + a + ")*(~(" + k + "*" + b + ")))";
   STEPS.pixelmath(ctx, { target: "main", expression: expr });
   s.forceClose();
   delete ctx.win.stars;
   return { expression: expr };
};

// ---------------------------------------------------------------- object-aware steps (galaxies, video ep2)

// Project the catalogue position/size (from AdP Messier.csv / NGC-IC.csv, passed by Python) into the image.
STEPS.locate_object = function (ctx, p) {
   var w = afWin(ctx, p);
   if (!w.hasAstrometricSolution) throw new Error("locate_object needs an astrometric solution");
   var md = new ImageMetadata();
   md.ExtractMetadata(w);
   var c = md.Convert_RD_I(new Point(p.ra, p.dec));
   if (!c) throw new Error("object position cannot be projected");
   var arcsecPx = md.resolution * 3600;
   var dec = p.dec * Math.PI / 180;
   var pn = md.Convert_RD_I(new Point(p.ra, p.dec + 0.05));
   var pe = md.Convert_RD_I(new Point(p.ra + 0.05 / Math.max(0.05, Math.cos(dec)), p.dec));
   var nx = pn.x - c.x, ny = pn.y - c.y, nl = Math.sqrt(nx * nx + ny * ny);
   var ex = pe.x - c.x, ey = pe.y - c.y, el = Math.sqrt(ex * ex + ey * ey);
   var pa = (p.posAngle || 0) * Math.PI / 180;      // position angle: from north through east
   var dx = Math.cos(pa) * nx / nl + Math.sin(pa) * ex / el, dy = Math.cos(pa) * ny / nl + Math.sin(pa) * ey / el;
   var a = (p.diameter || 10) * 60 / arcsecPx / 2;
   var b = a / (p.axisRatio || 1);
   var img = w.mainView.image;
   ctx.object = { cx: c.x, cy: c.y, a: a, b: b, angle: Math.atan2(dy, dx),
                  inImage: c.x >= 0 && c.y >= 0 && c.x < img.width && c.y < img.height };
   ctx.object.fillFraction = Math.PI * a * b / (img.width * img.height);
   return { cx: AF.round(c.x, 1), cy: AF.round(c.y, 1), semiMajorPx: AF.round(a, 1), semiMinorPx: AF.round(b, 1),
            angleDeg: AF.round(ctx.object.angle * 180 / Math.PI, 1), arcsecPerPx: AF.round(arcsecPx, 3),
            inImage: ctx.object.inImage, fillFraction: AF.round(ctx.object.fillFraction, 4) };
};

function afSolve(A, b) {   // Gaussian elimination with partial pivoting (small dense systems)
   var n = b.length, M = [];
   for (var i = 0; i < n; ++i) M.push(A[i].slice().concat([b[i]]));
   for (var c = 0; c < n; ++c) {
      var piv = c;
      for (var r = c + 1; r < n; ++r) if (Math.abs(M[r][c]) > Math.abs(M[piv][c])) piv = r;
      var t = M[c]; M[c] = M[piv]; M[piv] = t;
      if (Math.abs(M[c][c]) < 1e-15) throw new Error("singular background fit");
      for (r = c + 1; r < n; ++r) {
         var f = M[r][c] / M[c][c];
         for (var k = c; k <= n; ++k) M[r][k] -= f * M[c][k];
      }
   }
   var x = new Array(n);
   for (i = n - 1; i >= 0; --i) {
      var s = M[i][n];
      for (k = i + 1; k < n; ++k) s -= M[i][k] * x[k];
      x[i] = s / M[i][i];
   }
   return x;
}

function afPolyTerms(degree) {
   var t = [];
   for (var d = 0; d <= degree; ++d) for (var i = d; i >= 0; --i) t.push([i, d - i]);   // u^i v^j
   return t;
}

// Automatic DBE: grid samples (medians in boxes) away from the object and bright structures, robust 2-D
// polynomial per channel, subtracted with PixelMath while keeping the mean background level.
// Use when GradientCorrection would treat a large object as background (video ep2: GC failed on M31).
STEPS.dbe_auto = function (ctx, p) {
   var w = afWin(ctx, p), img = w.mainView.image, W = img.width, H = img.height, nc = img.numberOfChannels;
   var degree = p.degree || 2, nx = p.nx || 24, ny = p.ny || 16, box = p.box || Math.round(Math.min(W, H) / 60);
   var margin = p.margin == undefined ? 0.03 : p.margin, objScale = p.objectScale || 1.6;
   var o = ctx.object, samples = [];
   // catalogue sizes can be huge (M8 = 90' circle): shrink the exclusion until >= 40% of the grid is usable
   function excluded(x, y, k) {
      if (!o) return false;
      var c = Math.cos(o.angle), s = Math.sin(o.angle);
      var u = ((x - o.cx) * c + (y - o.cy) * s) / (o.a * k), v = (-(x - o.cx) * s + (y - o.cy) * c) / (o.b * k);
      return u * u + v * v < 1;
   }
   function gx(i) { return Math.round(W * (margin + (1 - 2 * margin) * (i + 0.5) / nx)); }
   function gy(j) { return Math.round(H * (margin + (1 - 2 * margin) * (j + 0.5) / ny)); }
   var scaleUsed = objScale;
   while (o && scaleUsed > 0.3) {
      var free = 0;
      for (var jj = 0; jj < ny; ++jj) for (var ii = 0; ii < nx; ++ii) if (!excluded(gx(ii), gy(jj), scaleUsed)) free++;
      if (free >= 0.4 * nx * ny) break;
      scaleUsed *= 0.8;
   }
   for (var j = 0; j < ny; ++j) for (var i = 0; i < nx; ++i) {
      var x = gx(i), y = gy(j);
      if (excluded(x, y, scaleUsed)) continue;
      var r = new Rect(Math.max(0, x - box), Math.max(0, y - box), Math.min(W, x + box), Math.min(H, y + box));
      var vals = [];
      for (var ch = 0; ch < nc; ++ch) { img.resetSelections(); img.selectedChannel = ch; img.selectedRect = r; vals.push(img.median()); }
      samples.push({ x: x, y: y, v: vals, lum: vals.reduce(function (a2, b2) { return a2 + b2; }, 0) / nc, ok: true });
   }
   img.resetSelections();
   // drop the brightest 15% outright (nebulosity, galaxy halo, bright stars), then iterate on residuals
   var lums = samples.map(function (q) { return q.lum; }).sort(function (a2, b2) { return a2 - b2; });
   var lumCut = lums[Math.floor(lums.length * 0.85)];
   samples.forEach(function (q) { if (q.lum > lumCut) q.ok = false; });
   var terms = afPolyTerms(degree), coefs = [];
   function basis(q) { var uu = 2 * q.x / W - 1, vv = 2 * q.y / H - 1; return terms.map(function (t) { return Math.pow(uu, t[0]) * Math.pow(vv, t[1]); }); }
   for (var it = 0; it < 5; ++it) {
      coefs = [];
      for (ch = 0; ch < nc; ++ch) {
         var A = [], bb = [], k = terms.length;
         for (var a1 = 0; a1 < k; ++a1) { var row = []; for (var z = 0; z < k; ++z) row.push(0); A.push(row); bb.push(0); }   // no Array.fill in PJSR
         samples.forEach(function (q) {
            if (!q.ok) return;
            var f = basis(q);
            for (var m = 0; m < k; ++m) { bb[m] += f[m] * q.v[ch]; for (var n2 = 0; n2 < k; ++n2) A[m][n2] += f[m] * f[n2]; }
         });
         coefs.push(afSolve(A, bb));
      }
      var res = [];
      samples.forEach(function (q) {
         var f = basis(q), e = 0;
         for (var c2 = 0; c2 < nc; ++c2) { var mv = 0; for (var m2 = 0; m2 < terms.length; ++m2) mv += coefs[c2][m2] * f[m2]; e += q.v[c2] - mv; }
         q.res = e / nc;
         if (q.ok) res.push(Math.abs(q.res));
      });
      res.sort(function (a2, b2) { return a2 - b2; });
      var mad = res[Math.floor(res.length / 2)] * 1.4826 + 1e-9, changed = 0;
      samples.forEach(function (q) {
         var keep = q.res < 2.5 * mad && q.res > -4 * mad;
         if (q.ok != keep && (q.ok || it < 4)) { q.ok = keep; changed++; }
      });
      if (!changed) break;
   }
   var used = samples.filter(function (q) { return q.ok; }).length;
   if (used < terms.length * 3) throw new Error("too few background samples (" + used + ") for degree " + degree);
   // model expressions; offset keeps the mean model level so the image stays linear and positive.
   // PixelMath symbol initialisers must be numeric literals, so u/v are assigned inside the expression.
   var pre = "u=2*x()/" + W + "-1; v=2*y()/" + H + "-1; ";
   var exprs = [], models = [], ranges = [];
   for (ch = 0; ch < nc; ++ch) {
      var poly = terms.map(function (t, m3) {
         return "(" + coefs[ch][m3].toExponential(10) + ")*" + "u^" + t[0] + "*v^" + t[1];
      }).join("+");
      var lo = 1e9, hi = -1e9, sum = 0, cnt = 0;
      for (var gy = 0; gy <= 10; ++gy) for (var gx = 0; gx <= 10; ++gx) {
         var f3 = basis({ x: W * gx / 10, y: H * gy / 10 }), mv3 = 0;
         for (var m4 = 0; m4 < terms.length; ++m4) mv3 += coefs[ch][m4] * f3[m4];
         lo = Math.min(lo, mv3); hi = Math.max(hi, mv3); sum += mv3; cnt++;
      }
      ranges.push([AF.round(lo, 7), AF.round(hi, 7)]);
      exprs.push(pre + "$T - (" + poly + ") + " + (sum / cnt).toExponential(10));
      models.push(pre + "(" + poly + ")");
   }
   function pm(list, newId) {
      var P = new PixelMath;
      P.symbols = "u, v";
      if (nc == 1) { P.expression = list[0]; P.useSingleExpression = true; }
      else { P.expression = list[0]; P.expression1 = list[1]; P.expression2 = list[2]; P.useSingleExpression = false; }
      P.rescale = false;
      if (newId) {
         P.createNewImage = true; P.showNewImage = false; P.newImageId = newId; P.truncate = false;
         P.newImageColorSpace = nc == 1 ? PixelMath.prototype.Gray : PixelMath.prototype.RGB;
         P.newImageSampleFormat = PixelMath.prototype.f32;
      } else { P.createNewImage = false; P.truncate = true; }
      if (!P.executeOn(w.mainView, false)) throw new Error("PixelMath failed in dbe_auto (see console.txt)");
   }
   var modelPreview = null;
   if (p.saveModel) {   // the model itself, so a reviewer can check it holds no object structure
      pm(models, "af_dbe_model");
      var mw = AF.windowById("af_dbe_model");
      modelPreview = AF.savePreview(mw.mainView, p.saveModel, 1200, true, false);
      mw.forceClose();
   }
   pm(exprs, null);
   return { samples: samples.length, used: used, degree: degree, modelRange: ranges, objectExcluded: !!o,
            objectScaleUsed: o ? AF.round(scaleUsed, 2) : null, modelPreview: modelPreview };
};

// EZ HDR (port of EZ_HDR.js by S. Dimant): HDRMultiscaleTransform on a copy, blended back through an
// inverted background range mask so only the bright parts (galaxy core) are compressed.
// p.ifBright: only when more than this share of pixels is above 0.97 (a burnt-out core such as M42's; on the starless
// image stars do not count).
STEPS.hdr = function (ctx, p) {
   var w = afWin(ctx, p);
   if (p.ifBright) {
      var share = AF.brightShare(w.mainView, 0.97);
      if (share < p.ifBright) return { skipped: "no bright core", brightShare: AF.round(share, 6) };
   }
   var layers = p.layers || 5, amount = p.amount == undefined ? 0.3 : p.amount;
   var PM = new PixelMath;
   PM.expression = w.mainView.image.isColor ? "CIEL($T)" : "$T";
   PM.useSingleExpression = true; PM.createNewImage = true; PM.showNewImage = false; PM.newImageId = "af_hdr_l";
   PM.newImageColorSpace = PixelMath.prototype.Gray; PM.newImageSampleFormat = PixelMath.prototype.f32;
   PM.executeOn(w.mainView, false);
   var L = AF.windowById("af_hdr_l");
   var med = L.mainView.image.median();
   var mask = AF.rangeMask(L.mainView, 0, med, 0.1, 5);
   L.forceClose();
   var clone = AF.duplicate(w.mainView, "af_hdr_clone");
   var H = new HDRMultiscaleTransform;
   H.numberOfLayers = layers;
   H.executeOn(clone.mainView, false);
   w.setMask(mask, true);
   w.maskEnabled = true;
   var B = new PixelMath;
   B.expression = "(1-" + amount + ")*$T + " + amount + "*af_hdr_clone";
   B.useSingleExpression = true; B.createNewImage = false;
   B.executeOn(w.mainView, false);
   w.removeMask();
   mask.forceClose(); clone.forceClose();
   return { layers: layers, amount: amount, maskMedian: AF.round(med, 5) };
};

// ---------------------------------------------------------------- mono cameras (video ep3: one master per filter)

// Register the listed windows onto the reference (StarAlignment with the windows as targets, as in the video; run on a
// view it leaves the image unchanged). Masters stacked on other nights, or by separate WBPP runs, are shifted and
// rotated against each other; registration resamples them into the reference's geometry, leaving empty borders that
// crop_common removes. Each registered image replaces its window under the same name.
STEPS.align_channels = function (ctx, p) {
   var names = (p.windows || []).filter(function (n) { return ctx.win[n]; });
   var ref = ctx.win[p.reference] ? p.reference : names[0];
   var targets = names.filter(function (n) { return n != ref; });
   if (!targets.length) return { reference: ref, aligned: [] };
   var S = new StarAlignment;
   S.referenceImage = ctx.win[ref].mainView.id; S.referenceIsFile = false;
   S.targets = targets.map(function (n) { return [true, false, ctx.win[n].mainView.id]; });
   S.generateDrizzleData = false; S.writeKeywords = false; S.onError = StarAlignment.prototype.Abort;
   afApply(S, p.hasOwnProperty("params") ? p.params : null);
   var before = AF.windowIds();
   if (!S.executeGlobal()) throw new Error("StarAlignment failed");
   var made = AF.newWindows(before), out = { reference: ref, aligned: [] };
   for (var i = 0; i < targets.length; ++i) {
      var id = ctx.win[targets[i]].mainView.id, reg = null;
      for (var j = 0; j < made.length; ++j) if (made[j].mainView.id.indexOf(id + "_") == 0) reg = made[j];
      if (!reg) throw new Error("StarAlignment made no registered image of " + targets[i]);
      ctx.win[targets[i]].forceClose();
      reg.mainView.id = id;
      reg.hide();
      ctx.win[targets[i]] = reg;
      out.aligned.push(targets[i]);
   }
   for (j = 0; j < made.length; ++j) if (out.aligned.every(function (n) { return ctx.win[n] !== made[j]; })) made[j].forceClose();
   return out;
};

// Crop every listed window to the area all of them cover: the sides move inwards while a border line of the
// coverage mask (1 where every channel has data) is not fully covered.
STEPS.crop_common = function (ctx, p) {
   var names = (p.windows || []).filter(function (n) { return ctx.win[n]; });
   var img = ctx.win[names[0]].mainView.image, W = img.width, H = img.height;
   var PM = new PixelMath;
   PM.expression = "iif(min(" + names.map(function (n) { return ctx.win[n].mainView.id; }).join(",") + ") > 0, 1, 0)";
   if (names.length == 1) PM.expression = "iif(" + ctx.win[names[0]].mainView.id + " > 0, 1, 0)";
   PM.useSingleExpression = true; PM.createNewImage = true; PM.showNewImage = false; PM.newImageId = "af_coverage";
   PM.newImageColorSpace = PixelMath.prototype.Gray; PM.newImageSampleFormat = PixelMath.prototype.f32;
   PM.executeOn(ctx.win[names[0]].mainView, false);
   var cw = AF.windowById("af_coverage"), cov = cw.mainView.image;
   function covered(x0, y0, x1, y1) { cov.selectedRect = new Rect(x0, y0, x1, y1); var m = cov.mean(); cov.resetSelections(); return m > 0.999; }
   var r = { x0: 0, y0: 0, x1: W, y1: H }, moved = true, limit = p.maxFraction || 0.25;
   while (moved) {
      moved = false;
      if (!covered(r.x0, r.y0, r.x1, r.y0 + 1)) { r.y0++; moved = true; }
      if (!covered(r.x0, r.y1 - 1, r.x1, r.y1)) { r.y1--; moved = true; }
      if (!covered(r.x0, r.y0, r.x0 + 1, r.y1)) { r.x0++; moved = true; }
      if (!covered(r.x1 - 1, r.y0, r.x1, r.y1)) { r.x1--; moved = true; }
      if (r.x1 - r.x0 < W * (1 - 2 * limit) || r.y1 - r.y0 < H * (1 - 2 * limit)) {
         cw.forceClose();
         throw new Error("the channels hardly overlap (common area " + (r.x1 - r.x0) + "x" + (r.y1 - r.y0) + " of " + W + "x" + H + ")");
      }
   }
   cw.forceClose();
   if (r.x0 == 0 && r.y0 == 0 && r.x1 == W && r.y1 == H) return { cropped: false, size: [W, H] };
   var m = p.margin == undefined ? 4 : p.margin;      // interpolation ringing next to the empty border
   var rect = [r.x0 + m, r.y0 + m, r.x1 - m, r.y1 - m];
   for (var i = 0; i < names.length; ++i) STEPS.crop(ctx, { target: names[i], rect: rect });
   return { cropped: true, rect: rect, from: [W, H] };
};

// R, G and B -> one colour image (video ep3: ChannelCombination). red / green / blue: a window name, or a PixelMath
// expression over window names (two dual-band colour masters, video ep5: "SO[0]", "(main[1] + main[2]) / 2"); one
// window may feed two channels (HOO: O makes G and B). output: the new window ("main" by default). The windows used are
// closed, or those in p.close. lum: the L window to make from the mean of the channels when there is none (mono R, G, B
// without L); false for narrowband palettes. solution: the window whose astrometric solution the result gets.
STEPS.combine_rgb = function (ctx, p) {
   var used = [];
   var exprs = [p.red || "main", p.green || "G", p.blue || "B"].map(function (e) {
      if (ctx.win[e]) { if (used.indexOf(e) < 0) used.push(e); return ctx.win[e].mainView.id; }
      if (/^[A-Za-z_]\w*$/.test(e)) throw new Error("combine_rgb: no window '" + e + "'");
      return e;
   });
   var geometry = ctx.win[used[0] || "main"];
   var PM = new PixelMath;
   PM.expression = exprs[0]; PM.expression1 = exprs[1]; PM.expression2 = exprs[2];
   PM.useSingleExpression = false; PM.createNewImage = true; PM.showNewImage = false; PM.newImageId = "af_rgb";
   PM.newImageColorSpace = PixelMath.prototype.RGB; PM.newImageSampleFormat = PixelMath.prototype.f32;
   PM.rescale = false; PM.truncate = true;
   PM.executeOn(geometry.mainView, false);
   var rgb = AF.windowById("af_rgb");
   var lumName = p.lum === false ? null : (p.lum || "L"), made = false;
   if (lumName && !ctx.win[lumName]) {
      var LM = new PixelMath;
      LM.expression = "(af_rgb[0] + af_rgb[1] + af_rgb[2]) / 3";
      LM.useSingleExpression = true; LM.createNewImage = true; LM.showNewImage = false; LM.newImageId = "af_lum";
      LM.newImageColorSpace = PixelMath.prototype.Gray; LM.newImageSampleFormat = PixelMath.prototype.f32;
      LM.executeOn(rgb.mainView, false);
      var lw = AF.windowById("af_lum");
      lw.hide();
      ctx.win[lumName] = lw;
      made = true;
   }
   rgb.keywords = geometry.keywords;      // focal length, pixel size, coordinates: what plate solving starts from
   var src = p.solution ? ctx.win[p.solution] : null;
   if (src && src.hasAstrometricSolution) rgb.copyAstrometricSolution(src);
   var output = p.output || "main";
   (p.close || used).concat(ctx.win[output] && used.indexOf(output) < 0 ? [output] : []).forEach(function (name) {
      var w = ctx.win[name];
      if (!w) return;
      delete ctx.win[name];
      w.forceClose();
   });
   rgb.mainView.id = output;
   rgb.hide();
   ctx.win[output] = rgb;
   if (made) ctx.win[lumName].mainView.id = lumName;
   return { output: output, from: exprs, lumFromRGB: made, solved: rgb.hasAstrometricSolution };
};

// Put the stretched L into the stretched colour image (video ep3: LRGBCombination with only L enabled). Saturation
// below 0.5 brings back the colour a bright L washes out (video: 0.40). The L window is closed afterwards.
STEPS.lrgb = function (ctx, p) {
   var w = afWin(ctx, p), lumName = p.lum || "L", lw = ctx.win[lumName];
   if (!lw) throw new Error("lrgb: no window '" + lumName + "'");
   var C = new LRGBCombination;
   // rows are R, G, B, L (the dialog lists L first): only L enabled
   C.channels = [[false, "", 1.0], [false, "", 1.0], [false, "", 1.0], [true, lw.mainView.id, 1.0]];
   C.mL = p.lightness == undefined ? 0.5 : p.lightness; C.mc = p.saturation == undefined ? 0.40 : p.saturation;
   C.clipHighlights = true; C.noiseReduction = false; C.inheritAstrometricSolution = true;
   afApply(C, p.hasOwnProperty("params") ? p.params : null);
   if (!C.executeOn(w.mainView, false)) throw new Error("LRGBCombination failed");
   lw.forceClose();
   delete ctx.win[lumName];
   return { lightness: C.mL, saturation: C.mc };
};

// ---------------------------------------------------------------- checkpoints & diagnostics

STEPS.save = function (ctx, p) {
   var w = afWin(ctx, p);
   AF.saveAs(w, p.path, p.bits);
   return { path: p.path };
};

STEPS.preview = function (ctx, p) {
   var w = afWin(ctx, p);
   var linear = p.linear == undefined ? ctx.linear : p.linear;
   var lk = p.linked == undefined ? !!ctx.colorCalibrated : p.linked;
   return { path: AF.savePreview(w.mainView, p.path, p.size || 1600, linear, lk) };
};

STEPS.measure = function (ctx, p) {
   var w = afWin(ctx, p);
   var out = { stats: AF.stats(w.mainView), noise: AF.noise(w.mainView), linear: ctx.linear,
               solved: w.hasAstrometricSolution };
   if (ctx.bgRect) out.background = AF.stats(w.mainView, afRect(ctx.bgRect));
   return out;
};
