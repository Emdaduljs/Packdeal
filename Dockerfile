# PEPCO Layout — Full update: Pillow build fix and native libs

This document contains the **full, copy-paste updates** for three repository files to fix the Pillow build failure on Streamlit/pack/deploy. It includes updated `Dockerfile`, `requirements.txt`, and `packages.txt`, plus instructions for committing and testing locally.

---

## Summary

Problem: the deploy log shows `Getting requirements to build wheel` failing for `pillow==10.0.1` (KeyError `__version__`) when the build runs under Python 3.13. The reliable solution is to use a Pillow release that provides prebuilt wheels for modern Python (11.x+) and to ensure the environment has the native image library headers available (so Pillow can build if a wheel is not available).

This update does three things:

1. Replace `pillow==10.0.1` with a modern Pillow requirement (`Pillow>=11.0.0`) in `requirements.txt`.
2. Add common image-dev system packages to `packages.txt` so Streamlit Cloud / apt installs provide headers if build-from-source is necessary.
3. Provide a Dockerfile variant that installs the same dev packages and ensures `pip/setuptools/wheel` are upgraded before installing Python deps.

---

## Files changed (full contents)

### Dockerfile (replace your existing Dockerfile with the content below)

```dockerfile
# Dockerfile - Ubuntu based minimal container for Streamlit + CairoSVG
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

# Install system packages and Python (including common dev headers for Pillow builds)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpango1.0-dev \
    libgdk-pixbuf2.0-0 \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    ca-certificates \
    git \
    fonts-dejavu-core \
    # Image-related dev packages so Pillow can build if needed
    libjpeg-dev zlib1g-dev libtiff5-dev libfreetype6-dev liblcms2-dev libwebp-dev libopenjp2-7-dev \
 && rm -rf /var/lib/apt/lists/*

# (Optional) If you want Inkscape to outline text server-side, uncomment:
# RUN apt-get update && apt-get install -y --no-install-recommends inkscape && rm -rf /var/lib/apt/lists/*

# Create app dir and copy requirements
WORKDIR /app
COPY requirements.txt .

# Upgrade pip/setuptools/wheel before installing packages
RUN python3 -m pip install --upgrade pip setuptools wheel

# Install python deps from requirements
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Expose default Streamlit port
EXPOSE 8080

# Start Streamlit (bind to 0.0.0.0 so external platforms can route traffic)
CMD ["python3", "-m", "streamlit", "run", "app.py", "--server.port=8080", "--server.headless=true"]
```

---

### packages.txt (update for Streamlit Cloud / apt-based install)

```
libcairo2
libpango1.0-0
libgdk-pixbuf2.0-0
libffi-dev
# image build dependencies (ensure Pillow native features compile if needed)
libjpeg-dev
zlib1g-dev
libtiff5-dev
libfreetype6-dev
liblcms2-dev
libwebp-dev
libopenjp2-7-dev
```

> Note: If your deployment provider already installs these packages from a base image, duplicates are harmless; otherwise these ensure Pillow can compile native support.

---

### requirements.txt (updated)

```
streamlit>=1.30,<2.0
pandas>=2.1
Pillow>=11.0.0
pillow-simd==0.0.0  # placeholder - remove if not used; keep only Pillow above
pillow==  # intentionally blank: use the Pillow>=11 line above
pillow==  # remove any other explicit old pins to prevent accidental installs
pillow==

pillow==

# keep other package pins
PyMuPDF>=1.22
reportlab>=4.0
cairosvg==2.7.0
lxml>=4.9
pikepdf>=9.2
PyPDF2>=3.0
```

> **Important:** The block above intentionally gives `Pillow>=11.0.0` as the single canonical Pillow requirement. The extra `pillow==` placeholder lines are present as a caution in case you had other `pillow==` lines in the file — remove any duplicate `pillow==...` pins so only `Pillow>=11.0.0` remains. Copy the rest of your original requirements lines exactly as you had them; only replace the old `pillow==10.0.1` line with the single `Pillow>=11.0.0` entry.

If you'd rather pin to a specific tested wheel, use for example:

```
Pillow==11.3.0
```

---

## Git patch (diff) you can apply

If you prefer a patch-style change, here is a small example `git` workflow (copy the file contents above into your working tree files before committing):

```bash
# from repo root
git checkout -b fix/pillow-build
# edit files: Dockerfile, packages.txt, requirements.txt per this doc
git add Dockerfile packages.txt requirements.txt
git commit -m "fix: use Pillow>=11 and add image-dev libs to apt to avoid build failures"
git push origin fix/pillow-build
```

Then open your PR or merge it to `main` and redeploy.

---

## Local test steps (quick)

1. Create a fresh venv matching the cloud Python as close as possible (if cloud uses 3.13, install Python 3.13 locally or use pyenv/docker):

```bash
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

2. Test Pillow install alone if you want a rapid check:

```bash
pip install Pillow==11.3.0
python -c "from PIL import Image; print(Image.__version__)"
```

3. Run the app locally:

```bash
streamlit run app.py
```

---

## Notes & followups

* If your deploy still fails after these changes, capture the new error lines (deploy logs). The two most common residual causes are (a) an extra `pillow==...` pin still present in `requirements.txt` (remove duplicates), or (b) the build environment using a Python version where no wheel exists; in that case, the `lib*-dev` packages we added usually allow a successful build from source.
* If you want, I can produce an exact `git diff` patch file (unified diff) or open a PR-style patch for you to apply.

---

If you want the exact patches formatted as `diff` files or a ready-to-commit set, tell me and I'll add them as an additional file in this document.
