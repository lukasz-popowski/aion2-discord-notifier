# AION 2 — EU/Phernos → Discord (PL)

Minimalistyczne powiadomienia o oficjalnych komunikatach gry AION 2 (Steam), po polsku, bez hostowania bota.

## Instrukcja wdrożenia

1. Utwórz **publiczne** repozytorium `aion2-discord-notifier` na GitHub i wgraj zawartość tej paczki do katalogu głównego (włącznie z ukrytym `.github/`). W publicznym repo GitHub-hosted standard Actions są darmowe. Nie dodawaj żadnych sekretów do kodu.
2. Discord → ustawienia kanału docelowego, np. `#aion2-news` → **Integracje → Webhooki → Nowy webhook → Kopiuj URL webhooka**. Traktuj URL jak hasło.
3. Google Cloud Console → utwórz projekt lub użyj dedykowanego → powiąż rozliczenia → włącz **Cloud Translation API**. W **APIs & Services → Credentials** utwórz **API key** i ogranicz ją do **Cloud Translation API**. Ustaw twardy limit liczby żądań API / dziennie (Cloud Translation API → Quotas), aby ograniczyć nieoczekiwane koszty. Uwaga: budżet GCP tylko ostrzega, nie blokuje naliczania.
4. GitHub → repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `DISCORD_WEBHOOK_URL` — pełny URL z Discorda
   - `GOOGLE_TRANSLATE_API_KEY` — klucz Google Cloud Translation
5. Repo → **Settings → Actions → General → Workflow permissions** → **Read and write permissions** (potrzebne do zapisu `state.json`).
6. Repo → **Actions → AION 2 notifications → Run workflow**. Pierwsze uruchomienie zapisze do historii istniejące ogłoszenia, **bez spamowania Discorda**. Dopiero kolejne nowe oficjalne ogłoszenia będą publikowane.
7. Sprawdź zakładkę Actions, czy workflow zakończył się pomyślnie. Harmonogram wykonuje się co 15 minut, z możliwymi opóźnieniami ze strony GitHub.

## Co trafia na Discord?

Ogłoszenia Steam o maintenance, patch notes, eventach i kodach, jeśli ich treść wskazuje EU, Phernos lub zakres globalny obejmujący Europę. Filtr jest konserwatywny: **niejednoznaczne ogłoszenia pomija**. Nie jest to oficjalny API status serwera Phernos. Nie pobiera treści z kanałów Discord ani ze stron PLAYNC. Komunikaty już przesyłane przez Discord Follow mogą pokrywać się z tymi z automatu — najlepiej użyć innego kanału.

## Limity i prywatność

- GitHub Actions: bez opłat na publicznym repo standard runner. Harmonogram 15 min.
- Cloud Translation NMT Basic: pierwsze 500 000 znaków/mies. objęte kredytem bez opłat **wg obecnego cennika**, ale aktywny billing jest wymagany; ceny i warunki mogą się zmieniać.
- W kodzie przyjęto **200 000 znaków/miesiąc** jako wewnętrzny limit. Limit ogranicza liczbę znaków wysyłanych przez ten skrypt, ale **nie stanowi gwarancji zerowego rachunku GCP** (inne aplikacje w tym projekcie, zmiany cennika, utrata stanu, wyjątki).
- Webhook i API key wyłącznie w GitHub Actions Secrets. URL webhooka nie powinien być nikomu udostępniany.
- `state.json` jest publiczny, zawiera tylko ID artykułów i lokalny licznik tłumaczeń, żadnych sekretów.

## Test lokalny

```bash
python -m unittest discover -s tests -v
python notifier.py --dry-run  # tylko podgląd, bez wysyłania na Discord
```

## Ważne ograniczenia

- Pierwszy start nie publikuje starych wiadomości, ponieważ chcemy uniknąć zalania kanału.
- Gdy dwie publikacje pojawią się między odpytywaniami, obsługiwane są obie (do 100 ostatnich na pobranie).
- Discord i Google mogą zwrócić błędy sieciowe. W przypadku częściowego sukcesu/przerwania workflow możliwe są duplikaty; logi Actions pomagają w diagnozie.
- API Steam może zwracać skróty lub formatowanie wiadomości; embed pokazuje max 3000 znaków opisu i link do oryginału.
- GitHub może automatycznie wyłączyć cykliczne workflow w publicznym repozytorium bez aktywności przez 60 dni. Wtedy należy ręcznie włączyć harmonogram.
