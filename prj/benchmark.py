import time
import unicodedata
import flag_search_core

# 1. Původní pomalá Python implementace
def python_strip(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def python_match(haystack, needle):
    if not haystack or not needle:
        return False
    return python_strip(needle).lower() in python_strip(haystack).lower()

# 2. Testovací data (simulace toho, co hledá uživatel)
test_statu = "Příliš žluťoučký kůň úpěl ďábelské ódy na Republiku São Tomé and Príncipe"
hledany_vyraz = "sao tome"
pocet_iteraci = 100000

print(f"Spouštím benchmark ({pocet_iteraci} iterací)...")
print("-" * 40)

# 3. Měření čistého Pythonu
start_py = time.perf_counter()
for _ in range(pocet_iteraci):
    python_match(test_statu, hledany_vyraz)
konec_py = time.perf_counter()
cas_py = konec_py - start_py

print(f"Čas čistého Pythonu: {cas_py:.4f} sekund")

# 4. Měření zkompilovaného Rustu
start_rust = time.perf_counter()
for _ in range(pocet_iteraci):
    flag_search_core.accent_insensitive_match(test_statu, hledany_vyraz)
konec_rust = time.perf_counter()
cas_rust = konec_rust - start_rust

print(f"Čas Rust rozšíření:  {cas_rust:.4f} sekund")
print("-" * 40)

# 5. Výsledek
if cas_rust > 0:
    zrychleni = cas_py / cas_rust
    print(f"VÝSLEDEK: Rust je {zrychleni:.2f}x rychlejší!")