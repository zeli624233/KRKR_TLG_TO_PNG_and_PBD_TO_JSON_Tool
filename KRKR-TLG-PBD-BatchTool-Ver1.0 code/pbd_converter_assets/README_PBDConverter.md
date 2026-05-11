# PBDConverter

**PBDConverter** is a simple, lightweight tool for converting between `.pbd` and `.json` file formats.

---

## 📦 Setup

1. **Clone the repository** (on a Windows machine):

```bash
git clone https://github.com/zhaomaoniu/PBDConverter.git
cd PBDConverter
```

2. **Required files**  
   Some essential files are not included in the repo. You’ll need to obtain and place them in the repo directory:

- `PBDConverter.exe`:  
  Download and extract [krkrz_20171225r2.7z](https://github.com/krkrz/krkrz/releases/tag/1.4.0r2).  
  Copy `tvpwin32.exe` into the repo directory and rename it to `PBDConverter.exe`.

- `json.dll` and `PackinOne.dll`:  
  These are usually found in your game’s `plugin` folder. Copy them into the repo directory as well.

---

## 🔧 Usage

### ▶️ Convert PBD to JSON

```bash
.\PBDConverter.exe -input="absolute/path/to/your/file.pbd"
```

- `-input`: Absolute path to the `.pbd` file to convert.

✅ **Example:**

```bash
.\PBDConverter.exe -input="D:\test.pbd"
```

📝 This will generate a `test.json` file in the same directory.

---

### ◀️ Convert JSON to PBD

```bash
.\PBDConverter.exe -input="absolute/path/to/your/file.json" -target="pbd"
```

- `-target`: Optional flag; defaults to `json`. Set to `pbd` to convert back to PBD format.

✅ **Example:**

```bash
.\PBDConverter.exe -input="D:\test.json" -target="pbd"
```

📝 This will generate a `test.pbd` file in the same directory.

---

## ⚠️ Disclaimer

This tool is provided for educational and research purposes only. I am not responsible for any consequences arising from its use.
