import streamlit as st
from PIL import Image
import io
import os
from utils import mockup, export

st.set_page_config(page_title="Pacdora Clone Full", layout="wide")

st.title("🎨 Pacdora Clone - Streamlit Full Project")

st.sidebar.header("Controls")

# scan models/ for 3D files
MODEL_DIR = "models"
model_files = []
if os.path.isdir(MODEL_DIR):
    model_files = sorted([f for f in os.listdir(MODEL_DIR)
                          if f.lower().endswith((".glb", ".gltf", ".obj"))])

# build template options: built-in templates + model files
builtin_templates = ["Water Bottle", "Gift Box"]
template_options = builtin_templates + model_files

uploaded_file = st.sidebar.file_uploader("Upload your design", type=["png", "jpg", "jpeg"])
template_choice = st.sidebar.selectbox("Choose a mockup template", template_options)

# If a model file is chosen, compute its path
if template_choice in model_files:
    template_is_model = True
    template_path = os.path.join(MODEL_DIR, template_choice)
else:
    template_is_model = False
    template_path = template_choice  # 'Water Bottle' / 'Gift Box'

if uploaded_file:
    design = Image.open(uploaded_file).convert("RGBA")
    st.subheader("Uploaded Design")
    st.image(design, caption="Your Design", use_container_width=True)

    if st.sidebar.button("Generate Mockup"):
        st.subheader(f"{template_choice} Mockup Preview")
        # pass template_path to generate_mockup (it can be builtin name or a file path)
        preview = mockup.generate_mockup(design, template_path)
        st.image(preview, caption=f"{template_choice} Mockup", use_container_width=True)

        # Export as PNG
        buf = io.BytesIO()
        preview.save(buf, format="PNG")
        st.download_button("⬇️ Download PNG Mockup", buf.getvalue(),
                           file_name=f"{template_choice.lower().replace(' ', '_')}_mockup.png",
                           mime="image/png")

        # Export as PDF
        pdf_buf = export.export_pdf(preview)
        if pdf_buf:
            st.download_button("⬇️ Download PDF Mockup", pdf_buf.getvalue(),
                               file_name=f"{template_choice.lower().replace(' ', '_')}_mockup.pdf",
                               mime="application/pdf")
else:
    st.info("👈 Upload a design from the sidebar to get started!")
