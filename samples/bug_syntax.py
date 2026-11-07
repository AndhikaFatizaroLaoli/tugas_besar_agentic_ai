def hitung_rata_rata(angka)
    total = 0
    for a in angka:
        total += a
    return total / len(angka)


data = [80, 90, 75]
print("Rata-rata:", hitung_rata_rata(data))
