#!/usr/bin/python3

import re
import sys



if len(sys.argv) != 3:
    exit("koriscenje " + sys.argv[0] + " Putanja do neke bash skripte pa naziv python skripte koju zelite da generisete ")

ulaznaPutanja = sys.argv[1]
izlaznaPutanja = sys.argv[2]


splitKomandeRegex = r'''"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|\S+'''
paternSplitKomande = re.compile(splitKomandeRegex) #patern za split unutar komande jer se unutar regexa za sed ili grep mogu naci spejsovi pa ne mozemo samo po spejsu splitovati
regexSedSplit = r"(?<!\\)/" 
paternSedSplit = re.compile(regexSedSplit) # patern za split u sedu(jer se unutar regexa mogu naci /)
regexHeadTail = r'-\d+'
paternHeadTail = re.compile(regexHeadTail)

regexBash = r"^(?!\s*#!|\s*$).+"
paternBash = re.compile(regexBash, re.MULTILINE) 
splitRegex = r"(?:'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.|[^|\"'])+"
splitPatern = re.compile(splitRegex, re.MULTILINE)  # patern za razbijanje komande jer se unutar regexa za sed i grep mogu naci |

try:
    f = open(ulaznaPutanja, "r")
    bashTekst = f.read()
    f.close()
except FileNotFoundError:
    exit("Neuspelo otvaranje bash skripte! ")

tekst = ""

definicijeFunkcija ={
"ucitajFajlove": """
def ucitajFajloveUTekst(imeFajlova):
    sadrzaj = []
    for sablon in imeFajlova:
        # glob.glob pretvara npr. 'nastava*.html' u listu pravih putanja
        listaFajlova = glob.glob(sablon)
        
        # Ako glob ne nadje nista, vraca praznu listu, pa probamo direktno ime
        if not listaFajlova:
            listaFajlova = [sablon]
            
        for putanja in listaFajlova:
            try:
                with open(putanja, 'r', encoding='utf-8') as f:
                    sadrzaj.append(f.read())
            except Exception as e:
                print(f"Upozorenje: Nije moguce citati {putanja}: {e}", file=sys.stderr)
                
    return "\\n".join(sadrzaj)
""",
"grep": """
def grepFunkcija(ulazniTekst, regex, flags):
    izlaz = []
    linije = ulazniTekst.splitlines()
    patern = re.compile(regex)
    
    COLOR, N, O, H = 1, 2, 4, 8
    
    ISKORISTIBOJU = (flags & COLOR) and sys.stdout.isatty() #provera da li smo u terminalu
    RED = "\\033[01;31m" if ISKORISTIBOJU else ""
    RESET = "\\033[0m" if ISKORISTIBOJU else ""

    for i, linija in enumerate(linije, 1):
        if patern.search(linija):
            prefix = f"{i}:" if (flags & N) else ""
            
            if (flags & O):
                for m in re.finditer(patern, linija):
                    izlaz.append(f"{prefix}{RED}{m.group(0)}{RESET}")
            else:
                if ISKORISTIBOJU:
                    obojenaLinija = patern.sub(f"{RED}\\\\g<0>{RESET}", linija)
                    izlaz.append(f"{prefix}{obojenaLinija}")
                else:
                    izlaz.append(f"{prefix}{linija}")
                    
    return "\\n".join(izlaz)
""",
"sed": """
def sedFunkcija(ulazniTekst, izrazZaZamenu, zamenskiIzraz, flags):
    izlaz = []
    linije = ulazniTekst.splitlines()
    patern = re.compile(izrazZaZamenu)
    zamenskiIzraz = re.sub(r'\\\\([1-9])',r'\\\\g<\\1>', zamenskiIzraz) #U pythonu moguce je uzeti 99 backreferenci a u sedu samo 9 pa ako se nadje negde \\20 python to shvata kao 20. grupu a sed kao 2. pa karakter 0 
    E = 1
    G = 2
    if flags & E:
        for linija in linije:
            if patern.search(linija):
                if flags & G:
                    linija = re.sub(patern, zamenskiIzraz, linija)
                else:
                    linija = re.sub(patern, zamenskiIzraz, linija, count=1)
            izlaz.append(f"{linija}")
    
    return "\\n".join(izlaz)
""",
"sort": """
def sortFunkcija(ulazniTekst, flags, column=None):
    if not ulazniTekst: return ""

    linije = [l for l in ulazniTekst.splitlines() if l.strip()]
    
    N, R = 1, 2
    
    
    def keyFunk(linija):
        delovi = linija.split()
        
        if column and 1 <= column <= len(delovi):
            vrednost = delovi[column-1]
        else:
            vrednost = linija
            
        if flags & N:
            try:
                return float(re.sub(r'[^0-9.-]', '', vrednost))
            except:
                return vrednost
        return vrednost

    linije.sort(key=keyFunk, reverse=bool(flags & R))
    return "\\n".join(linije)
""",
"uniq": """ 
def uniqFunkcija(ulazniTekst, flags):
    if not ulazniTekst: return ""
    linije = ulazniTekst.splitlines()
    C = 1
    br = 0
    izlaz = []
    if linije:
        for i in range(1, len(linije)):
            br += 1
            if linije[i] != linije[i-1]:
                if flags & C:
                    izlaz.append(str(br) + ' ' + linije[i - 1])
                else:
                    izlaz.append(linije[i - 1])
                br = 0
        if flags & C:
            izlaz.append(str(br) + ' ' + linije[len(linije) - 1])
        else:
            izlaz.append(linije[len(linije) - 1])    
    return "\\n".join(izlaz)
"""
}


class BashTranspiler:
    def __init__(self):
        self.korisceneFunkcije = set()  # Pratimo koje funkcije su potrebne.
        self.generisaniKod = [] 
        self.potrebanGlob = False
        self.tekstJePrazan = True

    def dodajFunkciju(self, ime):
        """Belezi koje funkcije su potrebne."""
        self.korisceneFunkcije.add(ime)

    def napraviZaglavlje(self):
        """Pravi zaglavlje sa potrebnim importima i funkcijama."""
        kod = ["import sys", "import re"]
        if self.potrebanGlob or "ucitajFajlove" in self.korisceneFunkcije:
            kod.append("import glob")
        
        kod.append("\n")
        for f in self.korisceneFunkcije:
            if f in definicijeFunkcija:
                kod.append(definicijeFunkcija[f])
             
        kod.append("\ntekst = None")
        return "\n".join(kod)

    def parse(self, komanda):
        komanda = komanda.strip()
        if not komanda:
            return ""
        
        deloviKomande = re.findall(paternSplitKomande, komanda)
        imeKomande = deloviKomande[0].strip()
        argumenti = deloviKomande[1:]

        izlazniKod = []
        
        if imeKomande in ["egrep", "grep"]:
            self.dodajFunkciju("grep")
            flagsGrep = 0
            COLOR, N, O, H = 1, 2, 4, 8

            i = 0

            while argumenti[i].startswith('-'):
                if argumenti[i] == '--color=auto': flagsGrep = flagsGrep | COLOR
                elif argumenti[i] == '-o': flagsGrep = flagsGrep | O
                elif argumenti[i] == '-h': flagsGrep = flagsGrep | H   
                elif argumenti[i] == '-n': flagsGrep = flagsGrep | N    
                i += 1
            regex = argumenti[i].strip("'\"")
            fajlovi = argumenti[i+1:]
            
            if not fajlovi:
                if self.tekstJePrazan:
                    izlazniKod.append("tekst = sys.stdin.read()")
            else: 
                self.dodajFunkciju("ucitajFajlove")
                izlazniKod.append(f"tekst = ucitajFajloveUTekst({fajlovi})")
            izlazniKod.append(f"tekst = grepFunkcija(tekst, r'{regex}', {flagsGrep})")
                        
        elif imeKomande == "sed":
            self.dodajFunkciju("sed")
            flagsSed = 0
            E, G = 1, 2
            
            i = 0
            while argumenti[i].startswith('-'):
                if argumenti[i] == '-E': flagsSed = flagsSed | E
                i += 1
            regex = argumenti[i].strip("'\"")
            if regex.endswith('g'): flagsSed = flagsSed | G

            sedLista = re.split(paternSedSplit, regex)
            fajlovi = argumenti[i+1:]
            if not fajlovi:
                if self.tekstJePrazan:
                    izlazniKod.append("tekst = sys.stdin.read()")
            else:
                self.dodajFunkciju("ucitajFajlove")
                izlazniKod.append(f"tekst = ucitajFajloveUTekst({fajlovi})")
                
            izlazniKod.append(f"tekst = sedFunkcija(tekst, r'{sedLista[1]}', r'{sedLista[2]}', {flagsSed})")
        
        elif imeKomande == "sort":
            self.dodajFunkciju("sort")
            flagsSort = 0
            NSORT, RSORT = 1, 2
            column = "None"
            fajlovi = []
            i = 0
            while i < len(argumenti):
                arg = argumenti[i]
                if arg == '-n': flagsSort |= NSORT    
                elif arg == '-r': flagsSort |= RSORT     
                elif arg == '-k':
                    i += 1
                    match = re.search(r'\d+', argumenti[i])
                    if match:
                        column = int(match.group())
                elif arg.startswith('-k'):
                    match = re.search(r'\d+', arg)
                    if match:
                        column = int(match.group())
                    i += 1
                else:
                    fajlovi.append(arg)
                
                i += 1
            if not fajlovi:
                if self.tekstJePrazan:
                    izlazniKod.append("tekst = sys.stdin.read()")
            else:
                self.dodajFunkciju("ucitajFajlove")
                izlazniKod.append(f"tekst = ucitajFajloveUTekst({fajlovi})")
                
            izlazniKod.append(f"tekst = sortFunkcija(tekst, {flagsSort}, {column})")

        
        elif imeKomande == "uniq":
            self.dodajFunkciju("uniq")
            flagsUniq = 0
            C = 1
            fajlovi = [arg for arg in argumenti if arg != '-c']
            if '-c' in argumenti: flagsUniq |= C
            
            if not fajlovi:
                if self.tekstJePrazan:
                    izlazniKod.append("tekst = sys.stdin.read()")
            else:
                self.dodajFunkciju("ucitajFajlove")
                izlazniKod.append(f"tekst = ucitajFajloveUTekst({fajlovi})")
                
            izlazniKod.append(f"tekst = uniqFunkcija(tekst, {flagsUniq})")
        
        elif imeKomande in ["head", "tail"]:
            n = 10
            fajlovi = []
            flagsHeadTail = 0
            N = 1
            i = 0
            while i < len(argumenti):
                if argumenti[i] == "-n" and i+1 < len(argumenti):
                    n = int(argumenti[i+1])
                    i += 2
                elif paternHeadTail.match(argumenti[i]):
                    n = int(argumenti[i][1:])
                    i += 1
                else:
                    fajlovi.append(argumenti[i])
                    i += 1
                
            if not fajlovi:
                if self.tekstJePrazan:
                    izlazniKod.append("tekst = sys.stdin.read()")
            else:
                self.dodajFunkciju("ucitajFajlove")
                izlazniKod.append(f"tekst = ucitajFajloveUTekst({fajlovi})")
            
            opseg = f":{n}" if imeKomande == "head" else f"-{n}:"
            izlazniKod.append(f"linije = tekst.splitlines()\ntekst = '\\n'.join(linije[{opseg}])")
        
        else: 
            return f"    # Komanda '{imeKomande}' nije podrzana"

        self.tekstJePrazan = False
        return "\n".join(izlazniKod)

transpiler = BashTranspiler()
teloSkripte = []


bashTekst = paternBash.findall(bashTekst)


komande = splitPatern.findall("".join(bashTekst))

for k in komande:
    print(k,file=sys.stderr)
    teloSkripte.append(transpiler.parse(k))

finalniKod = []
finalniKod.append("#!/usr/bin/python3")
finalniKod.append(transpiler.napraviZaglavlje())
finalniKod.extend(teloSkripte)

finalniKod.append("\nif tekst is not None:\n    print(tekst)")
try:
    f = open(izlaznaPutanja, "w")
    f.write("\n".join(finalniKod))
    f.close()
except IOError:
    exit("Greska pri upisu u izlaznu python skriptu")

print(f"Uspesno generisana skripta: {izlaznaPutanja}")