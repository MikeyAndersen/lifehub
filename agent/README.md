# LifeHub GPU boot-agent

Lille, selvstændigt script til gaming-PC'en (Windows, RX 7900 XTX). Ved boot venter det
til GPU'en er ledig, sikrer at Ollama kører, og kalder serverens
`POST /api/review/drain` indtil kvalitetskøen er tom (eller tidsboksen på 10 min udløber).
Til sidst aflæsses modellen fra VRAM og agenten afslutter. **Ingen periodisk genkørsel** —
beskeder der kommer senere fanges ved næste boot eller en manuel kørsel.

Kun Python 3.10+ standardbibliotek — ingen `pip install`.

## Opsætning

1. **Ollama på PC'en skal lytte på LAN.** Sæt system-miljøvariablen `OLLAMA_HOST=0.0.0.0`
   (Indstillinger → System → Om → Avancerede systemindstillinger → Miljøvariabler, eller
   `setx OLLAMA_HOST 0.0.0.0` og genstart Ollama). Åbn evt. Windows Firewall for port
   11434 på privat netværk. Uden dette svarer serveren `"online": false` ved drain.
   Hent den stærke model én gang: `ollama pull qwen2.5:32b-instruct`.
2. Kopiér `.env.example` til `.env` i denne mappe og udfyld:
   - `LIFEHUB_SERVER_URL` — serverens **LAN-adresse** (fx `http://192.168.0.145:8080`).
     Brug ikke den offentlige URL: Cloudflare Access svarer med login-redirect på
     `/api/review/drain`. På LAN er bearer-tokenet beskyttelsen.
   - `REVIEW_DRAIN_TOKEN` — samme hemmelighed som i serverens `.env`. Serveren afviser
     alt (403) hvis tokenet ikke matcher, og endpointet er helt lukket hvis serveren
     ikke har et token sat.
   - `OLLAMA_MODEL` — samme som serverens `STRONG_OLLAMA_MODEL`.
3. Test manuelt: `python gpu_agent.py --once` (én drain-runde, god til fejlsøgning).
   Log skrives både til konsollen og `agent.log` i denne mappe.

## Task Scheduler (kørsel ved boot)

1. Åbn **Task Scheduler** → *Create Task…*
2. **General:** navn fx "LifeHub GPU drain"; "Run only when user is logged on".
3. **Triggers:** *New…* → Begin the task: **At log on** (evt. med 1 min delay så
   Ollama/netværk er oppe).
4. **Actions:** *New…* → Program: `python` (eller fuld sti, fx
   `C:\Users\<dig>\AppData\Local\Programs\Python\Python312\python.exe`),
   Arguments: `gpu_agent.py`, **Start in:** denne mappes fulde sti.
5. **Conditions/Settings:** fjern "Stop if the computer switches to battery power"
   (desktop); sæt gerne "Stop the task if it runs longer than" til 1 time som bagstopper.

Uden argumenter bruger agenten boot-adfærden: vent til GPU < 30 % (målt via Windows'
`GPU Engine`-performance-countere — der findes ingen rocm-smi på Windows; kan counteren
ikke læses, fortsætter agenten med en advarsel), 10 minutters tidsboks.

## Manuel kørsel

| Kommando | Effekt |
|---|---|
| `python gpu_agent.py` | Som ved boot: 30 %-tjek, 10 min tidsboks |
| `python gpu_agent.py --now` | Spring GPU-tjekket over, start straks |
| `python gpu_agent.py --minutes 25` | Længere tidsboks |
| `python gpu_agent.py --minutes 30 --now` | Kombinerbart |
| `python gpu_agent.py --once` | Præcis én drain-runde, så exit |
| `drain.bat` (dobbeltklik) | Genvej til `--now` |

## Fejlsøgning

- **`Server answered 403`** — token i `agent/.env` matcher ikke serverens
  `REVIEW_DRAIN_TOKEN`, eller serveren har intet token sat.
- **`Server reports the strong Ollama unreachable`** — serveren kan ikke nå PC'ens
  Ollama: tjek `OLLAMA_HOST=0.0.0.0`, firewall port 11434, og at serverens
  `STRONG_OLLAMA_URL` peger på PC'ens aktuelle LAN-IP (overvej DHCP-reservation).
- **GPU-tjekket hænger** — kør med `--now`, eller tjek `typeperf "\GPU Engine(*)\Utilization Percentage" -sc 1` i en terminal.
