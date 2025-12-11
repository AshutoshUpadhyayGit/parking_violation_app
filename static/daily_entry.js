// static/daily_entry.js

if (!window.__dailyEntryInit) {
window.__dailyEntryInit = true;
(function () {

  if (window.dailyEntryLoaded) return;
  window.dailyEntryLoaded = true;
  // keep a set of already-rendered entry keys so repeated calls don't duplicate cards
  window.__renderedTodayEntryKeys = window.__renderedTodayEntryKeys || new Set();



  // helpers
  function $(id) { return document.getElementById(id); }

  function normalizeFlat(inp){
        const letters = (inp.match(/[A-Za-z]+/g) || []).join('').toUpperCase();
        const numbers = (inp.match(/[0-9]+/g) || []).join('');
        if (!letters || !numbers) return inp.toUpperCase();
        return `${letters}-${numbers}`;
    }


  async function fetchOwnerInfo(flatInput) {
        if (!flatInput) return null;
        try {
            const r = await fetch(`/api/owner_info?flat=${encodeURIComponent(flatInput)}`);
            return await r.json();
        } catch (e) {
            console.error("Owner lookup error:", e);
            return null;
        }
    }



  function nowIST() {
    try {
      const d = new Date();
      const utc = d.getTime() + (d.getTimezoneOffset() * 60000);
      const ist = new Date(utc + (5.5 * 3600000));
      return ist.toLocaleString('en-GB', { hour12: false });
    } catch (e) { return new Date().toLocaleString(); }
  }

  // elements
  const entryType = $('entryType');
  const vehicleSection = $('vehicleSection');
  const personSection = $('personSection');
  const last4 = $('last4');
  const fullPlate = $('fullPlate');
  const entryTime = $('entryTime');
  const purposeSelect = $('purposeSelect');
  const residentFields = $('residentFields');
  const flatNoResident = $('flatNoResident');

  const visitorFields = $('visitorFields');
  const flatToVisit = $('flatToVisit');
  const visitType = $('visitType');
  const otherDescriptionDiv = $('otherDescriptionDiv');
  const otherDescription = $('otherDescription');
  const entryImage = $('entryImage');

  const personCategory = $('personCategory');
  const personOtherDiv = $('personOtherDiv');
  const personOtherDescription = $('personOtherDescription');
  const personName = $('personName');
  const personFlatToVisit = $('personFlatToVisit');

  const personEntryTime = $('personEntryTime');
  const personContact = $('personContact');
  const vehicleContact = $('vehicleContact');
  const vehicleCallBtn = $('vehicleCallBtn');
  const callBtn = $('callBtn');


  // Auto timestamp on name typing
  personName.addEventListener('input', () => {
    personEntryTime.value = nowIST();
  });

  const saveBtn = $('saveBtn');
  const informOwnerBtn = $('informOwnerBtn');


  // Image preview
  const imageInput = document.getElementById('entryImage');
  const imagePreview = document.getElementById('imagePreview');
  const previewImg = document.getElementById('previewImg');

  if (imageInput) {
    imageInput.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        const reader = new FileReader();
        reader.onload = function (e) {
          previewImg.src = e.target.result;
          imagePreview.style.display = 'block';
        };
        reader.readAsDataURL(this.files[0]);
      } else {
        imagePreview.style.display = 'none';
      }
    });
  }

  // initial timestamps
  entryTime.value = nowIST();
  personEntryTime.value = nowIST();

//  function toggleSections() {
//    if (entryType.value === 'Vehicle') {
//      vehicleSection.style.display = '';
//      personSection.style.display = 'none';
//    } else {
//      vehicleSection.style.display = 'none';
//      personSection.style.display = '';
//    }
//  }

  function toggleSections(){
        if(entryType.value === 'Vehicle'){
            vehicleSection.style.display = '';
            personSection.style.display = 'none';

            // Vehicle default – disable until last4 is validated
            saveBtn.disabled = true;
            saveBtn.classList.add("disabled");

        } else {
            vehicleSection.style.display = 'none';
            personSection.style.display = '';

            // Person entries ALWAYS allowed → enable
            saveBtn.disabled = false;
            saveBtn.classList.remove("disabled");
        }
    }


  entryType.addEventListener('change', toggleSections);

  // Purpose logic
  purposeSelect.addEventListener('change', function () {
    if (purposeSelect.value === 'Resident') {
      residentFields.style.display = '';
      visitorFields.style.display = 'none';
    } else if (purposeSelect.value === 'Visitor') {
      residentFields.style.display = 'none';
      visitorFields.style.display = '';
    } else {
      residentFields.style.display = 'none';
      visitorFields.style.display = 'none';
    }
  });

  visitType.addEventListener('change', function () {
    otherDescriptionDiv.style.display = (visitType.value === 'Other') ? '' : 'none';
  });

  personCategory.addEventListener('change', function () {
    personOtherDiv.style.display = (personCategory.value === 'Other') ? '' : 'none';
  });

  // Fetch vehicle by last4
  last4.addEventListener('input', async function () {
    const v = last4.value.trim();
    if (v.length === 4) {
      entryTime.value = nowIST();
      try {
        const res = await fetch(`/api/find_vehicle?last4=${encodeURIComponent(v)}`);
        if (res.ok) {
          const j = await res.json();
          if (j.found) {
            // Disable save because resident vehicle entries are not allowed
            saveBtn.disabled = true;
            saveBtn.classList.add("disabled");

            fullPlate.value = j.vehicle.VehicleNo || '';
            purposeSelect.value = 'Resident';
            residentFields.style.display = '';
            flatNoResident.value = j.vehicle.FlatNo || '';
            visitorFields.style.display = 'none';
          } else {
            // Visitor → allow saving
            saveBtn.disabled = false;
            saveBtn.classList.remove("disabled");

            fullPlate.value = '';
            purposeSelect.value = 'Visitor';
            residentFields.style.display = 'none';
            visitorFields.style.display = '';
          }
        }
      } catch { }
    }
  });

  // Phone dialer button
    callBtn.addEventListener('click', () => {
        const num = personContact.value.trim();
        if (!num) {
            alert("No number entered");
            return;
        }
        window.location.href = `tel:${num}`;
    });


  vehicleCallBtn.addEventListener('click', () => {
        const num = vehicleContact.value.trim();
        if (!num) {
            alert("No number entered");
            return;
        }
        window.location.href = `tel:${num}`;
    });


  // ⬇️ NEW: normalize flat and fetch owner info from backend
    async function fetchOwnerInfoForFlat(rawFlat) {
      const flat = (rawFlat || '').trim();
      if (!flat) return null;

      const resp = await fetch(`/api/owner_info?flat=${encodeURIComponent(flat)}`);
      if (!resp.ok) return null;

      const data = await resp.json();
      // expected: { found: true/false, flat_normalized, owner_contact, parking_slot }
      if (!data.found) return null;
      return data;   // { owner_contact, parking_slot, flat_normalized }
    }


  document.getElementById('fetchOwnerBtn').addEventListener('click', async () => {
        document.getElementById("flatToVisit").value =
            document.getElementById("tower_flatToVisit").value + "-" +
            document.getElementById("flatNumber_flatToVisit").value.trim();

        const flat = flatToVisit.value.trim();
        const info = await fetchOwnerInfo(flat);

        if (!info || !info.found) {
            ownerContactField.value = "Not Available";
            parkingSlotField.value = "-";
            return;
        }

        ownerContactField.value = info.owner_contact || "Not Available";
        parkingSlotField.value = info.parking_slot || "-";
    });


    document.getElementById('fetchOwnerBtnPerson').addEventListener('click', async () => {
        document.getElementById("personFlatToVisit").value =
            document.getElementById("tower_personFlatToVisit").value + "-" +
            document.getElementById("flatNumber_personFlatToVisit").value.trim();

        const flat = personFlatToVisit.value.trim();
        const info = await fetchOwnerInfo(flat);

        if (!info || !info.found) {
            ownerContactFieldPerson.value = "Not Available";
            parkingSlotFieldPerson.value = "-";
            return;
        }

        ownerContactFieldPerson.value = info.owner_contact || "Not Available";
        parkingSlotFieldPerson.value = info.parking_slot || "-";
    });


  async function sendWhatsAppAfterSave() {

        let flat = (entryType.value === "Vehicle")
                    ? flatToVisit.value.trim()
                    : personFlatToVisit.value.trim();

        const info = await fetchOwnerInfo(flat);
        if (!info || !info.found || !info.owner_contact) {
            alert("Owner contact not available");
            return;
        }

        const now = new Date();
        const dateStr = now.toLocaleDateString('en-IN');
        const timeStr = now.toLocaleTimeString('en-IN');

        const phone = info.owner_contact;

        const imageUrl = previewImg && previewImg.src ? previewImg.src : null;

        // 📝 Build dynamic message
        let msg = `   🚨 *TenX Security - VISITOR Alert !!!* \n\n`;

        msg += `   *Approve (Y) or Reject (N) - As Visitor is waiting* \n\n`;

        msg += `*Flat:* ${flat}\n`;


        if (entryType.value === "Vehicle") {
            msg += `*Vehicle No (Last 4 digit):* ${last4.value || "-"}\n`;
        } else {
            msg += `*Visitor:* ${personName.value || "-"}\n`;
        }

        msg += `*Purpose:* ${purposeSelect.value}${visitType.value ? " - " + visitType.value : ""}\n`;
        msg += `*Parking Slot:* ${info.parking_slot || "-"}\n`;
        msg += `*Date:* ${dateStr}\n`;
        msg += `*Time:* ${timeStr}\n\n`;

        if (imageUrl) {
            msg += `*📷 Visitor Image is recorded by Security Team*\n\n`;
        }


        const url = `/whatsapp_redirect?phone=${phone}&msg=${encodeURIComponent(msg)}`;


        window.open(url, "_blank");
    }




  // SAVE handler
  saveBtn.addEventListener('click', async function () {

    entryTime.value = nowIST();
    personEntryTime.value = nowIST();

    if (entryType.value === 'Vehicle') {
      if (!last4.value.trim()) {
        alert("Please enter last 4 digits");
        return;
      }
      if (purposeSelect.value === 'Visitor' && visitType.value === 'Other' &&
        !otherDescription.value.trim()) {
        alert("Please fill 'Other' description");
        return;
      }

    } else {
      if (personCategory.value === 'Other' && !personOtherDescription.value.trim()) {
        alert("Please fill 'Other' description");
        return;
      }
    }

    // Build FormData
    const form = new FormData();
    form.append('type', entryType.value);

    if (entryType.value === 'Vehicle') {
      form.append('last4', last4.value.trim());
      form.append('full_plate', fullPlate.value || '');
      form.append('vehicle_category', '');
      form.append('owner_contact', vehicleContact.value || '');
      form.append('purpose_category', purposeSelect.value === 'Resident' ? 'Resident' : 'Visitor');
      form.append('purpose_subtype', purposeSelect.value === 'Resident' ? 'Resident' : visitType.value);
      form.append('flat_no', purposeSelect.value === 'Resident' ? flatNoResident.value || '' : flatToVisit.value || '');
//      form.append('description', visitType.value === 'Other' ? otherDescription.value : '');
      form.append('person_name', fullPlate.value || last4.value);


    } else {
      form.append('person_name', personName.value || '');
      form.append('person_contact', personContact.value || '');
      form.append('purpose_category', 'Person');
      form.append('purpose_subtype', personCategory.value);
      form.append('flat_no', personFlatToVisit.value || '');
      form.append('description', personOtherDescription.value || '');
    }

    // Image append
    if (imageInput && imageInput.files.length > 0) {
      form.append('image', imageInput.files[0]);
    }

    try {
      const resp = await fetch('/daily_entry', { method: 'POST', body: form });
      const j = await resp.json();

      if (resp.ok && j.status === 'success') {

        const banner = document.getElementById('successBanner');
        banner.style.display = 'block';
        setTimeout(() => banner.style.display = 'none', 3000);

        await sendWhatsAppAfterSave();


        // Reset everything
        last4.value = '';
        fullPlate.value = '';
        otherDescription.value = '';
        flatToVisit.value = '';
        personName.value = '';
        personOtherDescription.value = '';
        personFlatToVisit.value = '';
        personContact.value = '';
        vehicleContact.value = '';

        imageInput.value = '';
        imagePreview.style.display = 'none';

        entryType.value = 'Vehicle';
        saveBtn.disabled = true;
        saveBtn.classList.add("disabled");

        purposeSelect.value = 'Resident';
        visitType.value = 'Friend/Relative';
        personCategory.value = 'Friend/Relative';
        residentFields.style.display = 'none';
        visitorFields.style.display = 'none';
        personOtherDiv.style.display = 'none';

        toggleSections();
//        loadTodaysEntries();
        await loadTodaysEntries()

      } else {
        alert("Failed: " + j.message);
      }

    } catch (e) {
      console.error(e);
      alert("Network error");
    }

  });

  toggleSections();


  // ----------- Timestamp formatting ----------
  function ordinal(n) {
    const s = ["th", "st", "nd", "rd"], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  function formatStoredTimestamp(utcString) {
    let iso = utcString;
    if (typeof iso === 'string' && iso.indexOf('T') === -1 && iso.indexOf('+') !== -1) {
      iso = iso.replace(' ', 'T').replace(/\+00$/, '+00:00');
    }

    const d = new Date(iso);
    if (isNaN(d.getTime())) return utcString;

    const dd = d.toLocaleDateString('en-GB',
      { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }
    );
    const dayNum = d.getUTCDate();
    const dateWithOrdinal = `${ordinal(dayNum)} ${dd.split(' ').slice(1).join(' ')}`;

    const timeStr = d.toLocaleTimeString('en-IN',
      { hour: "2-digit", minute: "2-digit", hour12: true, timeZone: "UTC" }
    );

    return `${dateWithOrdinal} - ${timeStr}`;
  }

  // ----------- LOAD TODAY'S ENTRIES ----------
  // --- SAFE DEDUPE STORE ---
    window.__todayKeys = window.__todayKeys || new Set();

    async function loadTodaysEntries() {
      try {
        const res = await fetch('/api/todays_entries');
        const entries = await res.json();
        const container = document.getElementById('todaysEntries');

        // ALWAYS clear UI & dedupe set for a fresh clean render
        container.innerHTML = '';
        window.__todayKeys.clear();

        entries.forEach(e => {

          // --- UNIQUE KEY FOR DEDUPE ---
          const entryKey = (
            e.id ||
            e.entry_id ||
            (e.created_at + (e.full_plate || e.last4 || e.name || e.flat_no || ''))
          ).toString();

          if (window.__todayKeys.has(entryKey)) return;
          window.__todayKeys.add(entryKey);

          // ------- FIXED IMAGE NORMALIZER --------
          let imgs = [];

          if (Array.isArray(e.image_urls)) {
            imgs = e.image_urls;
          }
          else if (typeof e.image_urls === "string") {
            if (e.image_urls.trim().startsWith("[")) {
              try {
                const parsed = JSON.parse(e.image_urls);
                if (Array.isArray(parsed)) imgs = parsed;
              } catch {
                imgs = [];
              }
            }
            else if (e.image_urls.startsWith("http")) {
              imgs = [e.image_urls];
            }
          }

          //--------------------------------------

          const collapseId = "entry_" + Math.random().toString(36).substring(2, 8);
          const ts = formatStoredTimestamp(e.created_at);
          const [datePart, timePart] = ts.split(" - ");

          const card = document.createElement("div");
          card.className = "card mb-2 shadow-sm";

          card.innerHTML = `
            <div class="card-header d-flex justify-content-between align-items-center p-3"
                 style="cursor:pointer;"
                 data-bs-toggle="collapse"
                 data-bs-target="#${collapseId}"
                 aria-expanded="false"
                 aria-controls="${collapseId}">

              <div>
                  <div style="font-weight:700;">${timePart}</div>
                  <div style="font-size:0.85rem; color:#555;">${datePart}</div>
              </div>

              <div class="ms-3 text-end">
                  <div style="font-size:0.9rem; color:#444;">${e.entry_type || '-'}</div>
                  <div style="font-size:0.8rem; color:#777;">
                      ${e.purpose_category || ''}
                      ${e.purpose_subtype ? '(' + e.purpose_subtype + ')' : ''}
                  </div>
              </div>
            </div>

            <div id="${collapseId}" class="collapse">
              <div class="card-body">

                <div><strong>Type:</strong> ${e.entry_type || '-'}</div>
                <div><strong>Purpose:</strong> ${e.purpose_category || '-'}
                  ${e.purpose_subtype ? '(' + e.purpose_subtype + ')' : ''}</div>
                <div><strong>Flat:</strong> ${e.flat_no || '-'}</div>
                <div><strong>Owner Contact:</strong> ${e.owner_contact || "Not Available"}</div>
                <div><strong>Owner Parking Slot:</strong> ${e.parking_slot || "-"}</div>

                ${
                  e.entry_type === 'Vehicle'
                  ? `<div><strong>Vehicle No:</strong> ${e.full_plate || e.last4 || '-'}</div>`
                  : `<div><strong>Name:</strong> ${e.name || '-'}</div>`
                }

                <!-- VISITOR CONTACT WITH DIALER (KEEP THIS EXACTLY) -->
                ${
                  e.visitor_contact
                    ? `<div><strong>Visitor Contact:</strong>
                         <a href="tel:${e.visitor_contact}"
                            style="text-decoration:none; font-weight:bold;">
                            ${e.visitor_contact} 📞
                         </a>
                       </div>`
                    : ''
                }

                ${imgs.length > 0 ? `
                  <div class="mt-2">
                    <strong>Image:</strong><br>
                    <img src="${imgs[0]}"
                       class="entry-thumb"
                       data-img="${imgs[0]}"
                       style="width:80px; height:80px; object-fit:cover; border-radius:6px; cursor:pointer;">
                  </div>
                ` : ''}

              </div>
            </div>
          `;

          container.appendChild(card);
        });

      } catch (err) {
        console.error("Load entries error:", err);
      }
    }



  loadTodaysEntries();

  // Click to open large image
  document.addEventListener('click', function(e){
        if(e.target.classList.contains('entry-thumb')){
            const url = e.target.getAttribute('data-img');
            const modalImg = document.getElementById('modalImage');
            modalImg.src = url;
    
            const modal = new bootstrap.Modal(document.getElementById('imageModal'));
            modal.show();
        }
    });

  document.addEventListener('click', function(e){
        if(e.target.classList.contains('dial-btn')){
            const num = e.target.getAttribute('data-num');
            if (num) {
                window.location.href = `tel:${num}`;
            }
        }
    });



})();
}
