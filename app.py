import streamlit as st
from PIL import Image
import io
from utils import mockup, export

st.set_page_config(page_title="Pacdora Clone Full", layout="wide")

st.title("🎨 Pacdora Clone - Streamlit Full Project")

st.sidebar.header("Controls")
uploaded_file = st.sidebar.file_uploader("Upload your design", type=["png", "jpg", "jpeg"])
template = st.sidebar.selectbox("Choose a mockup template", ["Water Bottle", "Gift Box"])

if uploaded_file:
    design = Image.open(uploaded_file).convert("RGBA")
    st.subheader("Uploaded Design")
    st.image(design, caption="Your Design", use_container_width=True)

    if st.sidebar.button("Generate Mockup"):
        st.subheader(f"{template} Mockup Preview")
        preview = mockup.generate_mockup(design, template)
        st.image(preview, caption=f"{template} Mockup", use_container_width=True)

        # Export as PNG
        buf = io.BytesIO()
        preview.save(buf, format="PNG")
        st.download_button("⬇️ Download PNG Mockup", buf.getvalue(),
                           file_name=f"{template.lower().replace(' ', '_')}_mockup.png",
                           mime="image/png")

        # Export as PDF
        pdf_buf = export.export_pdf(preview)
        if pdf_buf:
            st.download_button("⬇️ Download PDF Mockup", pdf_buf.getvalue(),
                               file_name=f"{template.lower().replace(' ', '_')}_mockup.pdf",
                               mime="application/pdf")
else:
    st.info("👈 Upload a design from the sidebar to get started!")
