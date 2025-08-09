function bindCameraButtons() {
  const input = document.getElementById("photoInput");
  const form  = document.getElementById("mainForm");
  const take  = document.getElementById("takePhotoBtn");
  const pick  = document.getElementById("pickFromGalleryBtn");
  const clear = document.getElementById("clearPhotosBtn");
  const thumbs= document.getElementById("thumbs");
  const count = document.getElementById("fileCount");

  if (!input || !take || !pick) return;

  function updateThumbs(files) {
    thumbs.innerHTML = "";
    Array.from(files).forEach(file => {
      const img = document.createElement("img");
      img.alt = file.name;
      img.src = URL.createObjectURL(file);
      thumbs.appendChild(img);
    });
    count.textContent = files.length ? `${files.length} photo(s) selected` : "";
  }

  // “Take Photo”: prefer camera
  take.addEventListener("click", () => {
    input.removeAttribute("multiple");          // one at a time feels like story capture
    input.setAttribute("capture", "environment");
    input.click();
  });

  // “Choose from Gallery”
  pick.addEventListener("click", () => {
    input.setAttribute("multiple", "multiple");
    input.removeAttribute("capture");
    input.click();
  });

  input.addEventListener("change", () => updateThumbs(input.files));

  clear?.addEventListener("click", () => {
    const dt = new DataTransfer(); // empties FileList
    input.files = dt.files;
    updateThumbs([]);
  });
}

document.addEventListener("DOMContentLoaded", bindCameraButtons);
