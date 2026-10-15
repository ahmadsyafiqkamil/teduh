/**
 * UI translation table: Bahasa Indonesia (default) and English (judge toggle).
 *
 * CONCEPT §6.2 principle 5: "Bahasa Indonesia lebih dulu. Bahasa Inggris tersedia untuk
 * juri (toggle)." This module is that toggle. It holds every user-facing string in the web
 * app so the language switch flips the whole surface from one place.
 *
 * Convention: keys are flat dotted paths grouped by surface. Interpolation uses {name}
 * placeholders filled by t()'s params. Numbers never live here — they come from tools via
 * the SourceChip and are formatted by lib/format.ts.
 */

export type Lang = 'id' | 'en';

export type Message = string;

type Table = Record<string, Message>;

const id: Table = {
  // Header
  'header.coverage': 'DKI Jakarta · kelurahan',
  'header.layerGroup': 'Lapisan peta',
  'header.searchPlaceholder': 'Cari kelurahan…',
  'header.searchLabel': 'Cari kelurahan',
  'header.langGroup': 'Bahasa',
  'header.about': 'Tentang & Sumber Data',

  // Layers (segmented control + legend + map title)
  'layer.lst.label': 'Suhu Permukaan',
  'layer.lst.title': 'Suhu permukaan per kelurahan',
  'layer.lst.legendTitle': 'Suhu permukaan tanah (LST), °C',
  'layer.lst.legendSubtitle': 'Median musim kemarau 2023–2025 · Landsat 8/9 · bukan suhu udara',
  'layer.hvi.label': 'Kerentanan (HVI)',
  'layer.hvi.title': 'Kerentanan panas per kelurahan',
  'layer.hvi.legendTitle': 'Indeks Kerentanan Panas (HVI), 0–1',
  'layer.hvi.legendSubtitle':
    'Bahaya × keterpaparan, kepekaan (balita & lansia), dan kurangnya pohon',
  'layer.veg.label': 'Vegetasi',
  'layer.veg.title': 'Tutupan vegetasi per kelurahan',
  'layer.veg.legendTitle': 'Tutupan vegetasi, % luas kelurahan',
  'layer.veg.legendSubtitle': 'ESA WorldCover v200, 10 m · tutupan pohon dan mangrove',
  'layer.pop.label': 'Penduduk Rentan',
  'layer.pop.title': 'Kepadatan penduduk per kelurahan',
  'layer.pop.legendTitle': 'Penduduk, jiwa per km²',
  'layer.pop.legendSubtitle': 'WorldPop 2025, 100 m · model constrained, tervalidasi ke Dukcapil',
  'layer.dlst.label': 'ΔLST Simulasi',
  'layer.dlst.title': 'Perubahan suhu permukaan (ΔLST)',
  'layer.dlst.legendTitle': 'Perubahan suhu permukaan (ΔLST), °C',
  'layer.dlst.legendSubtitle': 'Hasil simulasi, indikatif · makin pekat makin turun',

  // Map overlays
  'map.zoomIn': 'Perbesar peta',
  'map.zoomOut': 'Perkecil peta',
  'map.priority': '{n} kelurahan prioritas dari jawaban agen',

  // Resize handles
  'resize.simulation': 'Ubah tinggi panel simulasi',
  'resize.agent': 'Ubah lebar panel agen',
  'resize.drawer': 'Ubah lebar panel profil',

  // Scenario dock
  'scenario.title': 'Simulasi skenario',
  'scenario.slider.tree.label': 'Tambah kanopi pohon',
  'scenario.slider.tree.help': 'Poin persen lahan terbuka',
  'scenario.slider.coolRoof.label': 'Cool roof',
  'scenario.slider.coolRoof.help': 'Porsi atap dicat pemantul panas',
  'scenario.slider.greenRoof.label': 'Green roof',
  'scenario.slider.greenRoof.help': 'Porsi atap beton datar',
  'scenario.budget': 'Anggaran (Rp)',
  'scenario.budgetLabel': 'Anggaran dalam rupiah',
  'scenario.simulate': 'Simulasikan',
  'scenario.calculating': 'Menghitung…',
  'scenario.multiSelect': 'Pilih banyak kelurahan',
  'scenario.clearPicked': 'Bersihkan ({n})',
  'scenario.multiHint.on': 'Klik kelurahan di peta untuk menambah atau menghapus pilihan.',
  'scenario.multiHint.off': 'Nyalakan untuk memilih beberapa kelurahan secara manual.',
  'scenario.clearResult': 'Hapus hasil',
  'scenario.status.empty': 'Belum ada simulasi. Atur intervensi, lalu tekan Simulasikan.',
  'scenario.status.pick':
    'Pilih kelurahan di peta atau minta agen menyusun prioritas dulu.',
  'scenario.status.failed': 'Simulasi gagal.',
  'scenario.status.treeBlocked':
    'Pohon tidak bisa ditanam — lahan terbangun penuh. Coba cool roof atau green roof.',
  'scenario.status.result':
    'Perkiraan rata-rata {mean} °C pada {n} kelurahan · indikatif, suhu permukaan.',
  'scenario.modeSimulate': 'Simulasikan',
  'scenario.modeOptimize': 'Optimalkan',
  'scenario.equityLabel': 'Porsi keadilan (0–1)',
  'scenario.equityHelp':
    'Porsi minimum anggaran ke kelurahan paling rentan. Kosongkan untuk 0,6.',
  'scenario.optimizeStatus.empty': 'Atur anggaran, lalu tekan Optimalkan.',
  'scenario.optimizeStatus.result': 'Portofolio tersusun: {n} paket · total {cost}.',
  'scenario.optimizeStatus.needBudget': 'Masukkan anggaran terlebih dahulu.',
  'scenario.optimizeStatus.trimmed':
    'Ditampilkan {n} kelurahan HVI-teratas dari pilihan Anda.',

  // Target labels
  'target.picked': 'Target: {n} kelurahan dipilih',
  'target.priority': 'Target: {n} kelurahan prioritas',
  'target.single': 'Target: 1 kelurahan terpilih',
  'target.none': 'Target: belum dipilih',

  // Agent panel
  'agent.title': 'Agen TEDUH',
  'agent.subtitle': 'Setiap angka berasal dari data atau model, bukan karangan',
  'agent.aria': 'Agen TEDUH',
  'agent.newThread': 'Percakapan baru',
  'agent.placeholder': 'Tanyakan tentang panas di wilayah Anda…',
  'agent.composerLabel': 'Pertanyaan untuk agen',
  'agent.cekAtap': 'Buka halaman Cek Atap',
  'agent.send': 'Kirim pertanyaan',
  'agent.steps.done': '{done} dari {total} langkah selesai',
  'agent.steps.seconds': '{seconds} detik',
  'agent.unreachable': 'Agen tidak bisa dihubungi.',

  // Tool step labels (keys are tool names)
  'tool.find_area': 'Mencari wilayah',
  'tool.get_area_profile': 'Mengambil profil kelurahan',
  'tool.rank_priority_areas': 'Menghitung indeks kerentanan',
  'tool.explain_drivers': 'Menganalisis faktor pendorong',
  'tool.simulate_intervention': 'Menyimulasikan intervensi',
  'tool.optimize_portfolio': 'Menyusun portofolio anggaran',
  'tool.get_evidence': 'Mengambil temuan literatur',
  'tool.get_session_facts': 'Mengumpulkan fakta percakapan',
  'tool.render_policy_brief': 'Menyusun policy brief',
  'tool.analyze_roof_photo': 'Menganalisis foto atap',
  'tool.recommend_roof_action': 'Menyusun rekomendasi atap',
  'tool.running': 'Menjalankan {tool}',

  // Drawer (profile)
  'drawer.aria': 'Profil kelurahan',
  'drawer.ariaNamed': 'Profil {name}',
  'drawer.close': 'Tutup profil',
  'drawer.kicker': 'PROFIL KELURAHAN',
  'drawer.loading': 'Memuat profil kelurahan…',
  'drawer.location': 'Kec. {kec} · {kota}',
  'drawer.rank': 'Peringkat HVI',
  'drawer.rankSource': '{source} Peringkat dihitung atas {total} kelurahan DKI Jakarta daratan.',
  'drawer.askAgent': 'Tanya agen tentang wilayah ini',
  'drawer.askPrompt': 'Jelaskan kondisi panas dan opsi intervensi untuk Kelurahan {name}.',
  'drawer.lst': 'LST rata-rata',
  'drawer.lstSub': 'suhu permukaan',
  'drawer.anomaly': 'Selisih dari rata-rata kota',
  'drawer.anomalySub': 'rata-rata kota',
  'drawer.anomalySource': '{source} Rata-rata kota dihitung dari sel berkualitas baik.',
  'drawer.hvi': 'Indeks kerentanan (HVI)',
  'drawer.hviSub': 'skala 0–1, makin tinggi makin rentan',
  'drawer.hviSource': '{source} HVI adalah persentil dalam-kota, bukan risiko absolut.',
  'drawer.vulnerable': 'Warga rentan',
  'drawer.vulnerableSource': '{source} Balita (<5 tahun) dan lansia (>=65 tahun), WorldPop 2025.',
  'drawer.exposedSuffix': 'di sel paling panas',
  'drawer.exposedSource': '{source} Warga rentan di sel dengan persentil bahaya >= 0,8.',
  'drawer.componentsTitle': 'Komponen kerentanan panas',
  'drawer.formula':
    'HVI = Bahaya × (0,4 Keterpaparan + 0,3 Kepekaan + 0,3 Kurangnya kapasitas adaptif)',
  'drawer.component.H': 'Bahaya (panas permukaan)',
  'drawer.component.E': 'Keterpaparan (kepadatan penduduk)',
  'drawer.component.S': 'Kepekaan (balita & lansia)',
  'drawer.component.A': 'Kurangnya kapasitas adaptif',
  'drawer.componentSource': '{source} Persentil dalam-kota untuk komponen {key}.',
  'drawer.driversTitle': 'Apa yang membuat wilayah ini panas?',
  'drawer.driversSub':
    'Kontribusi tiap faktor terhadap prediksi suhu, menurut model (SHAP).',
  'drawer.legendWarm': 'memanaskan',
  'drawer.legendCool': 'mendinginkan',
  'drawer.mismatch':
    'Jumlah kontribusi di atas {sum} **tidak menjumlah** ke selisih dari rata-rata kota. ' +
    'Keduanya besaran berbeda: model menjelaskan prediksinya sendiri, bukan selisih ' +
    'terhadap rata-rata kota. Pakai angka ini sebagai arah, bukan sebagai penguraian tepat.',
  'drawer.landcoverTitle': 'Tutupan lahan',
  'drawer.landcover.built': 'Bangunan',
  'drawer.landcover.tree': 'Pohon',
  'drawer.landcover.water': 'Air',
  'drawer.landcover.other': 'Lainnya',
  'drawer.landcoverSource.built': '{source} ESA WorldCover kelas 50.',
  'drawer.landcoverSource.tree': '{source} ESA WorldCover kelas 10 dan 95.',

  // Source chip
  'source.kicker.data': 'Sumber · Data satelit',
  'source.kicker.model': 'Sumber · Model & perhitungan TEDUH',
  'source.kicker.literatur': 'Sumber · Literatur',
  'source.kicker.asumsi': 'ASUMSI · dapat diedit',
  'source.kicker.input': 'Sumber · Masukan pengguna',

  // Result cards
  'result.rank.head': '{n} kelurahan paling rentan panas',
  'result.rank.col.rank': '#',
  'result.rank.col.kelurahan': 'Kelurahan',
  'result.rank.col.hvi': 'HVI',
  'result.rank.col.lst': 'LST',
  'result.rank.col.vulnerable': 'Rentan',
  'result.rank.footnote': 'LST = suhu permukaan, bukan suhu udara.',
  'result.rank.highlight': 'Sorot di peta',
  'result.simulate.head': 'Perkiraan dampak intervensi · indikatif',
  'result.simulate.deltaLst': 'Perubahan suhu permukaan',
  'result.simulate.popWeighted': 'Tertimbang penduduk',
  'result.simulate.vulnerableBenefiting': 'Warga rentan merasakan pendinginan',
  'result.simulate.vulnerableSource': '{source} Sel dengan pendinginan minimal 0,5 °C.',
  'result.simulate.cost': 'Perkiraan biaya',
  'result.simulate.treeBlocked':
    'Tidak ada lahan untuk menanam pohon di wilayah ini — hampir seluruh areanya sudah ' +
    'terbangun atau tertutup air. Coba intervensi cool roof atau green roof, yang bekerja ' +
    'di atas bangunan.',
  'result.simulate.evidence':
    'Pembanding literatur: {title} ({year}) melaporkan {min} sampai {max}',
  'result.simulate.evidenceNotComparable':
    ' — perhatikan bahwa studi ini mengukur besaran lain, bukan pendinginan kawasan.',
  'result.extrapolation.intro': 'Skenario ini **di luar rentang data latih** model untuk {labels}.',
  'result.extrapolation.albedo':
    'Pantulan permukaan setinggi ini belum pernah terpantau di Jakarta — belum ada atap ' +
    'reflektif di data latih — jadi angkanya ekstrapolasi fisika, bukan analog dari pengukuran.',
  'result.extrapolation.other':
    'Turunkan intensitas intervensi agar hasilnya lebih dapat diandalkan.',
  'result.optimize.head': 'Rekomendasi portofolio · {n} paket',
  'result.optimize.totalCost': 'Total biaya',
  'result.optimize.budget': 'Anggaran tersedia',
  'result.optimize.budgetSource': 'Anggaran yang Anda masukkan.',
  'result.optimize.unspent': 'Sisa anggaran',
  'result.optimize.unspentSource': 'Anggaran yang tidak terpakai oleh paket terpilih.',
  'result.optimize.equity': 'Porsi untuk kelurahan paling rentan',
  'result.optimize.equitySource': '{source} Kendala minimum {share}.',
  'result.optimize.quintile': 'kuintil teratas',

  // Intervention and level labels (used by the optimize package blocks)
  'intervention.cool_roof': 'Cool roof (cat pemantul)',
  'intervention.green_roof': 'Green roof (atap hijau)',
  'intervention.tree_planting': 'Tanam pohon',
  'level.low': 'intensitas rendah',
  'level.medium': 'intensitas sedang',
  'level.high': 'intensitas tinggi',
  'result.brief.badge': 'Policy brief',
  'result.brief.downloadPdf': 'Unduh PDF',
  'result.brief.downloadMd': 'Unduh Markdown',
  'result.brief.pdfFailed':
    'Render PDF gagal di server ini{error}. Brief tetap tersedia sebagai Markdown.',
  'result.brief.verified': 'Semua angka dalam brief diverifikasi terhadap fakta sesi.',

  // Feature labels (extrapolation + driver labels)
  'feature.albedo': 'pantulan permukaan (cool roof)',
  'feature.ndvi': 'kehijauan (vegetasi)',
  'feature.ndbi': 'indeks bangunan (NDBI)',
  'feature.ndwi': 'indeks kelembapan (NDWI)',
  'feature.tree_frac': 'tutupan pohon',
  'feature.built_frac': 'luas terbangun',
  'feature.water_frac': 'luas perairan',
  'feature.roof_frac': 'luas atap',
  'feature.bldg_h_mean': 'tinggi bangunan',
  'feature.elev_m': 'ketinggian lahan',
  'feature.dist_coast_km': 'jarak ke pantai',
  'feature.pop': 'jumlah penduduk',

  // Driver (SHAP) labels, matching teduh_agent/tools/areas.py FEATURE_LABELS.
  'driver.albedo': 'Albedo permukaan (daya pantul)',
  'driver.ndvi': 'Kerapatan vegetasi (NDVI)',
  'driver.ndbi': 'Indeks lahan terbangun (NDBI)',
  'driver.ndwi': 'Indeks kebasahan (NDWI)',
  'driver.tree_frac': 'Tutupan pohon',
  'driver.built_frac': 'Fraksi lahan terbangun',
  'driver.water_frac': 'Fraksi badan air',
  'driver.roof_frac': 'Fraksi atap bangunan',
  'driver.bldg_h_mean': 'Tinggi bangunan rata-rata',
  'driver.elev_m': 'Elevasi',
  'driver.dist_coast_km': 'Jarak ke pantai',
  'driver.pop': 'Kepadatan penduduk',

  // Sources (model/data description)
  'source.data': 'Data TEDUH v1 (Landsat 8/9, WorldPop 2025, ESA WorldCover v200).',
  'source.model': 'Model panas TEDUH LightGBM v1, spatial block CV.',
  'source.modelFull': 'Model panas TEDUH LightGBM v1 dengan monotonic constraints dan spatial block CV.',
  'source.dataFull':
    'Data TEDUH v1: Landsat 8/9 (median musim kemarau 2023–2025), Sentinel-2, ' +
    'ESA WorldCover v200, Google Open Buildings, WorldPop 2025.',
  'source.price': 'Harga satuan TEDUH, dapat disesuaikan (config/costs.yaml).',

  // Tool notes (returned as note_key by the backend, translated client-side)
  'note.indicative':
    'Angka ini perkiraan model untuk suhu PERMUKAAN (LST), bukan suhu udara, dan ' +
    'bersifat indikatif untuk penyaringan awal.',
  'note.lst_surface': 'Suhu permukaan (LST) dari Landsat 8/9, bukan suhu udara.',
  'note.shap_correlational':
    'Kontribusi dari model LightGBM (SHAP) dan bersifat korelasional, bukan sebab-akibat.',
  'note.optimize_costs':
    'Perkiraan biaya memakai harga satuan dari config/costs.yaml. Pendinginan adalah suhu ' +
    'permukaan dan bersifat indikatif.',

  // Cek Atap page
  'roof.title': 'Cek Atap',
  'roof.lead':
    'Foto atap rumah Anda, dan TEDUH akan mengenali jenisnya lalu menyarankan cara ' +
    'menurunkan panas yang masuk ke dalam rumah.',
  'roof.privacy':
    'jangan ada wajah, nomor rumah, plat nomor, atau nama jalan di dalam frame. Foto Anda ' +
    'tidak disimpan — foto hanya dianalisis, lalu langsung dibuang bersama seluruh metadatanya.',
  'roof.privacyPrefix': 'Sebelum memotret:',
  'roof.pick': 'Pilih foto atap',
  'roof.analyzing': 'Menganalisis foto…',
  'roof.fileHint': 'JPG atau PNG, maksimal 8 MB',
  'roof.pickLabel': 'Pilih foto atap',
  'roof.previewAlt': 'Pratinjau foto atap',
  'roof.analysisFailed': 'Analisis gagal.',
  'roof.kicker': 'YANG TERLIHAT DI FOTO',
  'roof.form': 'Bentuk atap',
  'roof.material': 'Material',
  'roof.confidence': 'Keyakinan analisis',

  // Roof materials / forms / actions
  'roof.material.clay_tile': 'Genteng tanah liat',
  'roof.material.concrete_tile': 'Genteng beton',
  'roof.material.metal_sheet': 'Seng atau metal',
  'roof.material.concrete_slab': 'Pelat beton',
  'roof.material.asbestos_cement': 'Asbes (semen berserat)',
  'roof.material.other': 'Lainnya',
  'roof.material.unknown': 'Belum bisa dipastikan',
  'roof.form.flat': 'Datar',
  'roof.form.pitched': 'Miring',
  'roof.form.mixed': 'Campuran',
  'roof.form.unknown': 'Belum bisa dipastikan',
  'roof.action.cool_roof': 'Cat cool roof (pemantul panas)',
  'roof.action.green_roof': 'Green roof (atap hijau)',
  'roof.action.maintain_shade': 'Pertahankan peneduh pohon',
  'roof.action.consult_professional': 'Konsultasi tenaga profesional',
  'roof.action.retake_photo': 'Perlu foto ulang',

  // Sumber data page
  'about.title': 'Tentang & Sumber Data',
  'about.lead':
    'TEDUH membantu pemerintah daerah memutuskan di mana dan intervensi apa yang paling ' +
    'efektif untuk mendinginkan kawasan paling panas dan paling rentan. Semua angka di ' +
    'aplikasi ini berasal dari data terbuka atau dari model yang dijelaskan di bawah — ' +
    'tidak ada angka yang dikarang.',
  'about.sourcesTitle': 'Sumber data',
  'about.modelTitle': 'Model panas',
  'about.dataPeriod': 'Periode data: {period}',
  'about.area': 'Wilayah: {area}',
  'about.trainCells': 'Data latih: {cells} sel pada {kel} kelurahan',
  'about.validation': 'Validasi: {scheme}',
  'about.r2':
    'R² rata-rata {r2}, lipatan terburuk {r2min}, RMSE {rmse} °C',
  'about.meetsTarget': 'memenuhi target {target}.',
  'about.missesTarget': 'belum mencapai target {target}.',
  'about.independentChecks': 'Pemeriksaan independen',
  'about.limitations': 'Keterbatasan',
};

const en: Table = {
  'header.coverage': 'DKI Jakarta · kelurahan',
  'header.layerGroup': 'Map layers',
  'header.searchPlaceholder': 'Search kelurahan…',
  'header.searchLabel': 'Search kelurahan',
  'header.langGroup': 'Language',
  'header.about': 'About & Data Sources',

  'layer.lst.label': 'Surface Temp.',
  'layer.lst.title': 'Surface temperature by kelurahan',
  'layer.lst.legendTitle': 'Land surface temperature (LST), °C',
  'layer.lst.legendSubtitle': 'Dry-season median 2023–2025 · Landsat 8/9 · not air temperature',
  'layer.hvi.label': 'Vulnerability (HVI)',
  'layer.hvi.title': 'Heat vulnerability by kelurahan',
  'layer.hvi.legendTitle': 'Heat Vulnerability Index (HVI), 0–1',
  'layer.hvi.legendSubtitle':
    'Hazard × exposure, sensitivity (under-5s & elderly), and lack of tree cover',
  'layer.veg.label': 'Vegetation',
  'layer.veg.title': 'Vegetation cover by kelurahan',
  'layer.veg.legendTitle': 'Vegetation cover, % of kelurahan area',
  'layer.veg.legendSubtitle': 'ESA WorldCover v200, 10 m · tree and mangrove cover',
  'layer.pop.label': 'Vulnerable People',
  'layer.pop.title': 'Population density by kelurahan',
  'layer.pop.legendTitle': 'Population, people per km²',
  'layer.pop.legendSubtitle': 'WorldPop 2025, 100 m · constrained model, validated to Dukcapil',
  'layer.dlst.label': 'ΔLST Simulation',
  'layer.dlst.title': 'Surface temperature change (ΔLST)',
  'layer.dlst.legendTitle': 'Surface temperature change (ΔLST), °C',
  'layer.dlst.legendSubtitle': 'Simulation result, indicative · deeper means cooler',

  'map.zoomIn': 'Zoom in',
  'map.zoomOut': 'Zoom out',
  'map.priority': '{n} priority kelurahan from the agent answer',

  'resize.simulation': 'Resize simulation panel',
  'resize.agent': 'Resize agent panel',
  'resize.drawer': 'Resize profile panel',

  'scenario.title': 'Scenario simulation',
  'scenario.slider.tree.label': 'Add tree canopy',
  'scenario.slider.tree.help': 'Percentage points of open land',
  'scenario.slider.coolRoof.label': 'Cool roof',
  'scenario.slider.coolRoof.help': 'Share of roofs painted heat-reflective',
  'scenario.slider.greenRoof.label': 'Green roof',
  'scenario.slider.greenRoof.help': 'Share of flat concrete roofs',
  'scenario.budget': 'Budget (Rp)',
  'scenario.budgetLabel': 'Budget in rupiah',
  'scenario.simulate': 'Simulate',
  'scenario.calculating': 'Calculating…',
  'scenario.multiSelect': 'Select multiple kelurahan',
  'scenario.clearPicked': 'Clear ({n})',
  'scenario.multiHint.on': 'Click kelurahan on the map to add or remove them.',
  'scenario.multiHint.off': 'Turn on to select several kelurahan manually.',
  'scenario.clearResult': 'Clear result',
  'scenario.status.empty': 'No simulation yet. Set interventions, then press Simulate.',
  'scenario.status.pick': 'Select a kelurahan on the map or ask the agent to rank priorities first.',
  'scenario.status.failed': 'Simulation failed.',
  'scenario.status.treeBlocked':
    'No room to plant trees — the area is almost fully built up. Try cool roof or green roof.',
  'scenario.status.result':
    'Estimated average {mean} °C across {n} kelurahan · indicative, surface temperature.',
  'scenario.modeSimulate': 'Simulate',
  'scenario.modeOptimize': 'Optimize',
  'scenario.equityLabel': 'Equity share (0–1)',
  'scenario.equityHelp':
    'Minimum budget share to the most vulnerable kelurahan. Leave empty for 0.6.',
  'scenario.optimizeStatus.empty': 'Set a budget, then press Optimize.',
  'scenario.optimizeStatus.result': 'Portfolio built: {n} packages · total {cost}.',
  'scenario.optimizeStatus.needBudget': 'Enter a budget first.',
  'scenario.optimizeStatus.trimmed':
    'Showing the {n} highest-HVI kelurahan from your selection.',

  'target.picked': 'Target: {n} kelurahan selected',
  'target.priority': 'Target: {n} priority kelurahan',
  'target.single': 'Target: 1 kelurahan selected',
  'target.none': 'Target: none selected',

  'agent.title': 'TEDUH Agent',
  'agent.subtitle': 'Every number comes from data or the model, never invented',
  'agent.aria': 'TEDUH Agent',
  'agent.newThread': 'New conversation',
  'agent.placeholder': 'Ask about heat in your area…',
  'agent.composerLabel': 'Question for the agent',
  'agent.cekAtap': 'Open Cek Atap page',
  'agent.send': 'Send question',
  'agent.steps.done': '{done} of {total} steps done',
  'agent.steps.seconds': '{seconds} seconds',
  'agent.unreachable': 'The agent could not be reached.',

  'tool.find_area': 'Finding the area',
  'tool.get_area_profile': 'Fetching the kelurahan profile',
  'tool.rank_priority_areas': 'Computing the vulnerability index',
  'tool.explain_drivers': 'Analysing driving factors',
  'tool.simulate_intervention': 'Simulating the intervention',
  'tool.optimize_portfolio': 'Building the budget portfolio',
  'tool.get_evidence': 'Fetching literature findings',
  'tool.get_session_facts': 'Collecting conversation facts',
  'tool.render_policy_brief': 'Drafting the policy brief',
  'tool.analyze_roof_photo': 'Analysing the roof photo',
  'tool.recommend_roof_action': 'Drafting the roof recommendation',
  'tool.running': 'Running {tool}',

  'drawer.aria': 'Kelurahan profile',
  'drawer.ariaNamed': 'Profile of {name}',
  'drawer.close': 'Close profile',
  'drawer.kicker': 'KELURAHAN PROFILE',
  'drawer.loading': 'Loading kelurahan profile…',
  'drawer.location': 'Kec. {kec} · {kota}',
  'drawer.rank': 'HVI rank',
  'drawer.rankSource': '{source} Rank computed over {total} kelurahan in mainland DKI Jakarta.',
  'drawer.askAgent': 'Ask the agent about this area',
  'drawer.askPrompt': 'Explain the heat conditions and intervention options for {name}.',
  'drawer.lst': 'Mean LST',
  'drawer.lstSub': 'surface temperature',
  'drawer.anomaly': 'Difference from city mean',
  'drawer.anomalySub': 'city mean',
  'drawer.anomalySource': '{source} City mean computed from good-quality cells.',
  'drawer.hvi': 'Vulnerability index (HVI)',
  'drawer.hviSub': '0–1 scale, higher means more vulnerable',
  'drawer.hviSource': '{source} HVI is an in-city percentile, not absolute risk.',
  'drawer.vulnerable': 'Vulnerable residents',
  'drawer.vulnerableSource': '{source} Under-5s and 65+ (WorldPop 2025).',
  'drawer.exposedSuffix': 'in the hottest cells',
  'drawer.exposedSource': '{source} Vulnerable residents in cells with hazard percentile ≥ 0.8.',
  'drawer.componentsTitle': 'Heat vulnerability components',
  'drawer.formula':
    'HVI = Hazard × (0.4 Exposure + 0.3 Sensitivity + 0.3 Lack of adaptive capacity)',
  'drawer.component.H': 'Hazard (surface heat)',
  'drawer.component.E': 'Exposure (population density)',
  'drawer.component.S': 'Sensitivity (under-5s & elderly)',
  'drawer.component.A': 'Lack of adaptive capacity',
  'drawer.componentSource': '{source} In-city percentile for the {key} component.',
  'drawer.driversTitle': 'What makes this area hot?',
  'drawer.driversSub':
    'Each factor’s contribution to the predicted temperature, per the model (SHAP).',
  'drawer.legendWarm': 'warming',
  'drawer.legendCool': 'cooling',
  'drawer.mismatch':
    'The contributions above ({sum}) **do not add up** to the difference from the city mean. ' +
    'They are different quantities: the model explains its own prediction, not the gap from ' +
    'the city mean. Treat these as direction, not an exact decomposition.',
  'drawer.landcoverTitle': 'Land cover',
  'drawer.landcover.built': 'Buildings',
  'drawer.landcover.tree': 'Trees',
  'drawer.landcover.water': 'Water',
  'drawer.landcover.other': 'Other',
  'drawer.landcoverSource.built': '{source} ESA WorldCover class 50.',
  'drawer.landcoverSource.tree': '{source} ESA WorldCover classes 10 and 95.',

  'source.kicker.data': 'Source · Satellite data',
  'source.kicker.model': 'Source · TEDUH model & computation',
  'source.kicker.literatur': 'Source · Literature',
  'source.kicker.asumsi': 'ASSUMPTION · editable',
  'source.kicker.input': 'Source · User input',

  'result.rank.head': '{n} most heat-vulnerable kelurahan',
  'result.rank.col.rank': '#',
  'result.rank.col.kelurahan': 'Kelurahan',
  'result.rank.col.hvi': 'HVI',
  'result.rank.col.lst': 'LST',
  'result.rank.col.vulnerable': 'Vulnerable',
  'result.rank.footnote': 'LST = surface temperature, not air temperature.',
  'result.rank.highlight': 'Highlight on map',
  'result.simulate.head': 'Estimated intervention impact · indicative',
  'result.simulate.deltaLst': 'Surface temperature change',
  'result.simulate.popWeighted': 'Population-weighted',
  'result.simulate.vulnerableBenefiting': 'Vulnerable residents feeling cooling',
  'result.simulate.vulnerableSource': '{source} Cells with at least 0.5 °C cooling.',
  'result.simulate.cost': 'Estimated cost',
  'result.simulate.treeBlocked':
    'No room to plant trees here — almost the whole area is built up or water. Try ' +
    'cool roof or green roof, which work on top of buildings.',
  'result.simulate.evidence':
    'Literature comparison: {title} ({year}) reported {min} to {max}',
  'result.simulate.evidenceNotComparable':
    ' — note that this study measures a different quantity, not area cooling.',
  'result.extrapolation.intro': 'This scenario is **outside the training range** of the model for {labels}.',
  'result.extrapolation.albedo':
    'Reflectivity this high has never been observed in Jakarta — there are no reflective ' +
    'roofs in the training data — so the figure is physics extrapolation, not a measured analogue.',
  'result.extrapolation.other':
    'Lower the intervention intensity for more reliable results.',
  'result.optimize.head': 'Portfolio recommendation · {n} packages',
  'result.optimize.totalCost': 'Total cost',
  'result.optimize.budget': 'Available budget',
  'result.optimize.budgetSource': 'The budget you entered.',
  'result.optimize.unspent': 'Unspent budget',
  'result.optimize.unspentSource': 'Budget not consumed by the chosen packages.',
  'result.optimize.equity': 'Share for the most vulnerable kelurahan',
  'result.optimize.equitySource': '{source} Minimum constraint {share}.',
  'result.optimize.quintile': 'top quintile',

  // Intervention and level labels (used by the optimize package blocks)
  'intervention.cool_roof': 'Cool roof (reflective coating)',
  'intervention.green_roof': 'Green roof',
  'intervention.tree_planting': 'Tree planting',
  'level.low': 'low intensity',
  'level.medium': 'medium intensity',
  'level.high': 'high intensity',
  'result.brief.badge': 'Policy brief',
  'result.brief.downloadPdf': 'Download PDF',
  'result.brief.downloadMd': 'Download Markdown',
  'result.brief.pdfFailed':
    'PDF rendering failed on this server{error}. The brief is still available as Markdown.',
  'result.brief.verified': 'Every figure in the brief is verified against session facts.',

  'feature.albedo': 'surface reflectivity (cool roof)',
  'feature.ndvi': 'greenness (vegetation)',
  'feature.ndbi': 'built-up index (NDBI)',
  'feature.ndwi': 'wetness index (NDWI)',
  'feature.tree_frac': 'tree cover',
  'feature.built_frac': 'built-up area',
  'feature.water_frac': 'water area',
  'feature.roof_frac': 'roof area',
  'feature.bldg_h_mean': 'building height',
  'feature.elev_m': 'elevation',
  'feature.dist_coast_km': 'distance to coast',
  'feature.pop': 'population',

  'driver.albedo': 'Surface albedo (reflectivity)',
  'driver.ndvi': 'Vegetation density (NDVI)',
  'driver.ndbi': 'Built-up index (NDBI)',
  'driver.ndwi': 'Wetness index (NDWI)',
  'driver.tree_frac': 'Tree cover',
  'driver.built_frac': 'Built-up fraction',
  'driver.water_frac': 'Water fraction',
  'driver.roof_frac': 'Building roof fraction',
  'driver.bldg_h_mean': 'Mean building height',
  'driver.elev_m': 'Elevation',
  'driver.dist_coast_km': 'Distance to coast',
  'driver.pop': 'Population density',

  'source.data': 'TEDUH data v1 (Landsat 8/9, WorldPop 2025, ESA WorldCover v200).',
  'source.model': 'TEDUH heat model LightGBM v1, spatial block CV.',
  'source.modelFull': 'TEDUH heat model LightGBM v1 with monotonic constraints and spatial block cross-validation.',
  'source.dataFull':
    'TEDUH data v1: Landsat 8/9 (dry-season median 2023–2025), Sentinel-2, ' +
    'ESA WorldCover v200, Google Open Buildings, WorldPop 2025.',
  'source.price': 'TEDUH unit prices, adjustable (config/costs.yaml).',

  'note.indicative':
    'This figure is the model estimate of SURFACE temperature (LST), not air temperature, ' +
    'and is indicative for initial screening.',
  'note.lst_surface': 'Surface temperature (LST) from Landsat 8/9, not air temperature.',
  'note.shap_correlational':
    'Contributions from the LightGBM model (SHAP) and are correlational, not causal.',
  'note.optimize_costs':
    'Cost estimates use unit prices from config/costs.yaml. Cooling is surface temperature ' +
    'and is indicative.',

  'roof.title': 'Roof Check',
  'roof.lead':
    'Photograph your roof and TEDUH will recognise its type and suggest how to reduce the ' +
    'heat entering your home.',
  'roof.privacy':
    'keep faces, house numbers, licence plates, and street names out of the frame. Your ' +
    'photo is not stored — it is only analysed, then discarded along with all metadata.',
  'roof.privacyPrefix': 'Before photographing:',
  'roof.pick': 'Choose a roof photo',
  'roof.analyzing': 'Analysing photo…',
  'roof.fileHint': 'JPG or PNG, up to 8 MB',
  'roof.pickLabel': 'Choose a roof photo',
  'roof.previewAlt': 'Roof photo preview',
  'roof.analysisFailed': 'Analysis failed.',
  'roof.kicker': 'WHAT THE PHOTO SHOWS',
  'roof.form': 'Roof form',
  'roof.material': 'Material',
  'roof.confidence': 'Analysis confidence',

  'roof.material.clay_tile': 'Clay tile',
  'roof.material.concrete_tile': 'Concrete tile',
  'roof.material.metal_sheet': 'Metal sheet',
  'roof.material.concrete_slab': 'Concrete slab',
  'roof.material.asbestos_cement': 'Asbestos (fibre cement)',
  'roof.material.other': 'Other',
  'roof.material.unknown': 'Not yet determined',
  'roof.form.flat': 'Flat',
  'roof.form.pitched': 'Pitched',
  'roof.form.mixed': 'Mixed',
  'roof.form.unknown': 'Not yet determined',
  'roof.action.cool_roof': 'Cool roof paint (heat-reflective)',
  'roof.action.green_roof': 'Green roof',
  'roof.action.maintain_shade': 'Keep tree shade',
  'roof.action.consult_professional': 'Consult a professional',
  'roof.action.retake_photo': 'Photo needs retaking',

  'about.title': 'About & Data Sources',
  'about.lead':
    'TEDUH helps local government decide where and which interventions are most effective at ' +
    'cooling the hottest and most vulnerable areas. Every figure in this app comes from open ' +
    'data or from the model explained below — nothing is invented.',
  'about.sourcesTitle': 'Data sources',
  'about.modelTitle': 'Heat model',
  'about.dataPeriod': 'Data period: {period}',
  'about.area': 'Area: {area}',
  'about.trainCells': 'Training data: {cells} cells across {kel} kelurahan',
  'about.validation': 'Validation: {scheme}',
  'about.r2': 'Mean R² {r2}, worst fold {r2min}, RMSE {rmse} °C',
  'about.meetsTarget': 'meets the {target} target.',
  'about.missesTarget': 'does not yet meet the {target} target.',
  'about.independentChecks': 'Independent checks',
  'about.limitations': 'Limitations',
};

const TABLES: Record<Lang, Table> = { id, en };

/**
 * Translate a key, filling {placeholders} from params.
 *
 * Missing keys fall back to the key itself so a typo is visible on screen rather than
 * silently rendering nothing. That is the same philosophy as the tools' error paths: a
 * loud failure beats a silent one.
 */
export function t(lang: Lang, key: string, params: Record<string, string | number> = {}): string {
  const table = TABLES[lang] ?? id;
  let text = table[key] ?? id[key] ?? key;
  for (const [name, value] of Object.entries(params)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
}

export { TABLES };
