"""Dokumen Knowledge Base internal: panduan perbaikan error Python."""

KB_DOCS = [
    {
        "doc_id": "KB-001",
        "title": "SyntaxError: titik dua (:) hilang pada def/if/for/while/class",
        "keywords": "SyntaxError expected ':' titik dua colon def if elif else for while class try except",
        "content": (
            "Penyebab: pernyataan blok (def, if, elif, else, for, while, class, try, except) "
            "wajib diakhiri tanda titik dua. Python melaporkan SyntaxError: expected ':'.\n"
            "Perbaikan: tambahkan ':' di akhir baris header blok.\n"
            "Contoh salah : def hitung(a)\n"
            "Contoh benar : def hitung(a):"
        ),
    },
    {
        "doc_id": "KB-002",
        "title": "SyntaxError: tanda kurung atau kutip tidak ditutup",
        "keywords": "SyntaxError '(' was never closed unterminated string literal kurung kurawal bracket parenthesis kutip",
        "content": (
            "Penyebab: kurung ( [ { atau tanda kutip dibuka tetapi tidak ditutup. Error sering "
            "dilaporkan pada baris SETELAH kesalahan sebenarnya.\n"
            "Perbaikan: cocokkan setiap pembuka dengan penutupnya, periksa baris sebelum baris error.\n"
            "Contoh salah : print('halo'\n"
            "Contoh benar : print('halo')"
        ),
    },
    {
        "doc_id": "KB-003",
        "title": "IndentationError: indentasi tidak konsisten atau blok kosong",
        "keywords": "IndentationError expected an indented block unindent does not match spasi tab indentasi",
        "content": (
            "Penyebab: isi blok tidak menjorok, atau campuran spasi dan tab.\n"
            "Perbaikan: gunakan 4 spasi per level, jangan campur tab dan spasi; isi blok kosong dengan 'pass'."
        ),
    },
    {
        "doc_id": "KB-004",
        "title": "NameError: variabel atau fungsi belum didefinisikan",
        "keywords": "NameError name is not defined variabel typo nama belum didefinisikan",
        "content": (
            "Penyebab: nama dipakai sebelum diberi nilai, salah ketik, atau di luar scope.\n"
            "Perbaikan: definisikan variabel sebelum dipakai, periksa ejaan nama, pastikan import sudah ada."
        ),
    },
    {
        "doc_id": "KB-005",
        "title": "TypeError: menggabungkan teks dengan angka",
        "keywords": "TypeError gabung teks string angka integer tipe data tidak cocok operand",
        "content": (
            "Penyebab: operator + dipakai antara tipe str dan int (atau tipe berbeda lain).\n"
            "Perbaikan: ubah angka ke teks dengan str(umur), atau gunakan f-string.\n"
            "Contoh salah : 'Umur ' + umur\n"
            "Contoh benar : 'Umur ' + str(umur)   atau   f'Umur {umur}'"
        ),
    },
    {
        "doc_id": "KB-006",
        "title": "ZeroDivisionError: pembagian dengan nol",
        "keywords": "ZeroDivisionError division by zero pembagian nol pembagi len list kosong rata-rata",
        "content": (
            "Penyebab: pembagi bernilai 0, misalnya len(list_kosong) saat menghitung rata-rata.\n"
            "Perbaikan: tambahkan guard sebelum pembagian, mis. 'if len(angka) == 0: return 0' "
            "(atau raise ValueError dengan pesan jelas)."
        ),
    },
    {
        "doc_id": "KB-007",
        "title": "IndexError: indeks list di luar jangkauan",
        "keywords": "IndexError list index out of range indeks urutan array batas loop",
        "content": (
            "Penyebab: mengakses indeks >= len(list) atau list kosong.\n"
            "Perbaikan: periksa len() sebelum mengakses, gunakan range(len(x)) dengan benar, "
            "atau iterasi langsung 'for item in x'."
        ),
    },
    {
        "doc_id": "KB-008",
        "title": "KeyError: kunci dictionary tidak ada",
        "keywords": "KeyError dictionary dict kunci key tidak ada get",
        "content": (
            "Penyebab: mengakses kunci yang belum ada pada dict.\n"
            "Perbaikan: gunakan d.get('kunci', default) atau periksa dengan 'if kunci in d'."
        ),
    },
    {
        "doc_id": "KB-009",
        "title": "AttributeError: objek None tidak punya atribut",
        "keywords": "AttributeError NoneType object has no attribute sort append in-place return None",
        "content": (
            "Penyebab: variabel bernilai None, sering karena method in-place (list.sort(), list.append()) "
            "mengembalikan None lalu hasilnya ditimpa ke variabel.\n"
            "Perbaikan: jangan menugaskan hasil method in-place; gunakan sorted(x) bila butuh salinan."
        ),
    },
    {
        "doc_id": "KB-010",
        "title": "ValueError: konversi string ke angka gagal",
        "keywords": "ValueError invalid literal for int() with base 10 konversi float input angka",
        "content": (
            "Penyebab: int('abc') atau input pengguna bukan angka.\n"
            "Perbaikan: validasi dengan str.isdigit() atau bungkus dengan try/except ValueError."
        ),
    },
    {
        "doc_id": "KB-011",
        "title": "FileNotFoundError: berkas tidak ditemukan",
        "keywords": "FileNotFoundError No such file or directory open path berkas file",
        "content": (
            "Penyebab: path salah atau working directory berbeda.\n"
            "Perbaikan: periksa path dengan os.path.exists / pathlib.Path(...).exists(), gunakan path absolut."
        ),
    },
    {
        "doc_id": "KB-012",
        "title": "ModuleNotFoundError: modul tidak terpasang atau salah nama",
        "keywords": "ModuleNotFoundError ImportError No module named import pip install modul library",
        "content": (
            "Penyebab: library belum terpasang atau nama import salah.\n"
            "Perbaikan: pip install <paket>, cek ejaan import, pastikan virtual environment aktif."
        ),
    },
    {
        "doc_id": "KB-013",
        "title": "RecursionError: rekursi tanpa kondisi berhenti",
        "keywords": "RecursionError maximum recursion depth exceeded rekursi base case fungsi memanggil diri sendiri",
        "content": (
            "Penyebab: fungsi rekursif tidak punya base case atau tidak mendekati base case.\n"
            "Perbaikan: tambahkan base case yang pasti tercapai, atau ubah menjadi iterasi."
        ),
    },
    {
        "doc_id": "KB-014",
        "title": "Infinite loop: perulangan tidak pernah berhenti (timeout)",
        "keywords": "TimeoutError infinite loop while True perulangan tak berhenti kondisi increment counter",
        "content": (
            "Penyebab: kondisi while tidak pernah menjadi False karena variabel kontrol tidak diubah.\n"
            "Perbaikan: pastikan variabel kontrol di-update di dalam loop (mis. i += 1) atau gunakan break."
        ),
    },
    {
        "doc_id": "KB-015",
        "title": "TypeError: jumlah argumen fungsi tidak sesuai",
        "keywords": "TypeError missing required positional argument takes positional arguments but were given argumen parameter fungsi",
        "content": (
            "Penyebab: fungsi dipanggil dengan argumen lebih sedikit atau lebih banyak dari definisinya.\n"
            "Perbaikan: samakan jumlah argumen pemanggilan dengan parameter fungsi, atau beri nilai default."
        ),
    },
]
