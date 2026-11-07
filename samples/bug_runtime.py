def hitung_rata_rata(angka):
    total = 0
    for a in angka:
        total += a
    return total / len(angka)


nilai_kelas_a = [80, 90, 75]
nilai_kelas_b = []
print("Kelas A:", hitung_rata_rata(nilai_kelas_a))
print("Kelas B:", hitung_rata_rata(nilai_kelas_b))
