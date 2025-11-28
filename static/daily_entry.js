// static/daily_entry.js
(function(){
  // helpers
  function $(id){ return document.getElementById(id); }
  function nowIST(){
    // show local time in IST string
    try {
      const d = new Date();
      // convert to IST offset (+5:30)
      const utc = d.getTime() + (d.getTimezoneOffset() * 60000);
      const ist = new Date(utc + (5.5 * 3600000));
      return ist.toLocaleString('en-GB', { hour12:false });
    } catch(e) { return new Date().toLocaleString(); }
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

  // Auto-update timestamp when person name typed
  personName.addEventListener('input', () => {
        personEntryTime.value = nowIST();
  });



  const saveBtn = $('saveBtn');

  // initial
  entryTime.value = nowIST();
  personEntryTime.value = nowIST();

  function toggleSections(){
    if(entryType.value === 'Vehicle'){
      vehicleSection.style.display = '';
      personSection.style.display = 'none';
    } else {
      vehicleSection.style.display = 'none';
      personSection.style.display = '';
    }
  }

  entryType.addEventListener('change', function(){
    toggleSections();
  });

  purposeSelect.addEventListener('change', function(){
    if(purposeSelect.value === 'Resident'){
      residentFields.style.display = '';
      visitorFields.style.display = 'none';
    } else if(purposeSelect.value === 'Visitor'){
      residentFields.style.display = 'none';
      visitorFields.style.display = '';
    } else {
      residentFields.style.display = 'none';
      visitorFields.style.display = 'none';
    }
  });

  visitType.addEventListener('change', function(){
    if(visitType.value === 'Other'){
      otherDescriptionDiv.style.display = '';
    } else {
      otherDescriptionDiv.style.display = 'none';
    }
  });

  personCategory.addEventListener('change', function(){
    if(personCategory.value === 'Other'){
      personOtherDiv.style.display = '';
    } else {
      personOtherDiv.style.display = 'none';
    }
  });

  // when last4 length is 4 -> attempt to fetch vehicle from server (optional)
  last4.addEventListener('input', async function(){
    const v = last4.value.trim();
    if(v.length === 4){
      // update entry time immediately
      entryTime.value = nowIST();
      // Query server to find matching vehicle (calls back to /daily_entry via GET param? we'll use fetch to endpoint below)
      try {
        const res = await fetch(`/api/find_vehicle?last4=${encodeURIComponent(v)}`);
        if(res.ok){
          const j = await res.json();
          if(j.found){
            fullPlate.value = j.vehicle.VehicleNo || '';
            // auto-select Resident if found
            purposeSelect.value = 'Resident';
            residentFields.style.display = '';
            flatNoResident.value = j.vehicle.FlatNo || '';
            visitorFields.style.display = 'none';
          } else {
            fullPlate.value = '';
            // assume visitor by default
            purposeSelect.value = 'Visitor';
            residentFields.style.display = 'none';
            visitorFields.style.display = '';
          }
        } else {
          fullPlate.value = '';
          purposeSelect.value = 'Visitor';
          residentFields.style.display = 'none';
          visitorFields.style.display = '';
        }
      } catch(e){
        fullPlate.value = '';
        purposeSelect.value = 'Visitor';
        residentFields.style.display = 'none';
        visitorFields.style.display = '';
      }
    }
  });

  // Save handler
  saveBtn.addEventListener('click', async function(){
    // Refresh timestamp just before saving
    entryTime.value = nowIST();
    personEntryTime.value = nowIST();

    // validation
    if(entryType.value === 'Vehicle'){
      const v = last4.value.trim();
      if(!v || v.length < 1){
        alert("Please enter last 4 digits.");
        return;
      }
      if(purposeSelect.value === 'Visitor' && visitType.value === 'Other'){
        if(!otherDescription.value.trim()){
          alert("Please describe 'Other' (mandatory).");
          return;
        }
      }
    } else {
      // Person validations
      if(personCategory.value === 'Other' && !personOtherDescription.value.trim()){
        alert("Please describe 'Other' for person (mandatory).");
        return;
      }
      if(!personName.value.trim()){
        if(!confirm("Person name is empty. Continue without name?")) return;
      }
    }

    // prepare payload
    let payload = {};
    if(entryType.value === 'Vehicle'){
      payload.type = 'Vehicle';
      payload.last4 = last4.value.trim();
      payload.full_plate = fullPlate.value || '';
      payload.vehicle_category = ''; // optional
      payload.purpose_category = (purposeSelect.value === 'Resident' ? 'Resident' : 'Visitor');
//      payload.purpose_subtype = visitType.value;
      // purpose_subtype fix:
      if (purposeSelect.value === 'Resident') {
            payload.purpose_subtype = 'Resident';   // force correct subtype
      } else {
            payload.purpose_subtype = visitType.value;
      }

      payload.flat_no = (purposeSelect.value === 'Resident') ? flatNoResident.value || '' : flatToVisit.value || '';
      payload.description = (visitType.value === 'Other') ? otherDescription.value : '';
    } else {
      payload.type = 'Person';
      payload.person_name = personName.value || '';
      payload.purpose_category = 'Person';
      payload.purpose_subtype = personCategory.value;
      payload.flat_no = personFlatToVisit.value || '';
      payload.description = personOtherDescription.value || '';
    }

    // send POST
//    try {
//      const resp = await fetch('/daily_entry', {
//        method: 'POST',
//        headers: {'Content-Type':'application/json'},
//        body: JSON.stringify(payload)
//      });
//      const j = await resp.json();
//      if(resp.ok && j.status === 'success'){
////        alert('Entry saved');
//        // Show green success toast
////        const toastEl = document.getElementById('successToast');
////        const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
////        toast.show();
//        // Show centered success banner
//        const banner = document.getElementById('successBanner');
//        banner.style.display = 'block';
//        setTimeout(() => {
//            banner.style.display = 'none';
//        }, 3000);
//
//
//        // reset minimal fields
//        last4.value = '';
//        fullPlate.value = '';
//        flatToVisit.value = '';
//        otherDescription.value = '';
//        personName.value = '';
//        personOtherDescription.value = '';
//        personFlatToVisit.value = '';
//        entryTime.value = nowIST();
//        personEntryTime.value = nowIST();
//        purposeSelect.value = 'Resident';
//        toggleSections();
//        entryType.value = 'Vehicle';
//        toggleSections();
//
//        visitType.value = 'Friend/Relative';
//        otherDescriptionDiv.style.display = 'none';
//        otherDescription.value = '';
//
//        residentFields.style.display = 'none';
//        visitorFields.style.display = 'none';
//        personOtherDiv.style.display = 'none';
//
//        personCategory.value = 'Friend/Relative';
//        personName.value = '';
//        personFlatToVisit.value = '';
//        loadTodaysEntries();
//
//      } else {
//        alert('Failed to save entry: ' + (j.message || 'unknown'));
//      }
//    } catch(e){
//      console.error(e);
//      alert('Network error while saving entry');
//    }


        // send POST using FormData (works with or without file)
    try {
      const form = new FormData();

      // Common fields
      form.append('type', entryType.value);
      if(entryType.value === 'Vehicle'){
        form.append('last4', last4.value.trim());
        form.append('full_plate', fullPlate.value || '');
        form.append('vehicle_category', '');
        form.append('purpose_category', purposeSelect.value === 'Resident' ? 'Resident' : 'Visitor');
        form.append('purpose_subtype', (purposeSelect.value === 'Resident') ? 'Resident' : visitType.value);
        form.append('flat_no', (purposeSelect.value === 'Resident') ? flatNoResident.value || '' : flatToVisit.value || '');
        form.append('description', (visitType.value === 'Other') ? otherDescription.value : '');
      } else {
        form.append('person_name', personName.value || '');
        form.append('person_contact', personContact.value || '');
        form.append('purpose_category', 'Person');
        form.append('purpose_subtype', personCategory.value);
        form.append('flat_no', personFlatToVisit.value || '');
        form.append('description', personOtherDescription.value || '');
      }

      // Append image if selected
      const imageInput = document.getElementById('entryImage');
      if(imageInput && imageInput.files && imageInput.files.length > 0){
        // only the first file is used (as requested)
        form.append('image', imageInput.files[0]);
      }

      const resp = await fetch('/daily_entry', {
        method: 'POST',
        body: form
      });

      // parse JSON
      const j = await resp.json();

      if(resp.ok && j.status === 'success'){
        // show success banner (your existing code)
        const banner = document.getElementById('successBanner');
        banner.style.display = 'block';
        setTimeout(() => { banner.style.display = 'none'; }, 3000);

        // clear all fields (existing reset logic)
        last4.value = '';
        fullPlate.value = '';
        flatToVisit.value = '';
        otherDescription.value = '';
        personName.value = '';
        personOtherDescription.value = '';
        personFlatToVisit.value = '';
        personContact.value = '';
        entryTime.value = nowIST();
        personEntryTime.value = nowIST();
        purposeSelect.value = 'Resident';
        entryType.value = 'Vehicle';
        toggleSections();

        visitType.value = 'Friend/Relative';
        otherDescriptionDiv.style.display = 'none';
        otherDescription.value = '';
        residentFields.style.display = 'none';
        visitorFields.style.display = 'none';
        personOtherDiv.style.display = 'none';
        personCategory.value = 'Friend/Relative';
        personName.value = '';
        personFlatToVisit.value = '';

        // clear file input
        if(imageInput) imageInput.value = '';

        // refresh today's entries
        loadTodaysEntries();

      } else {
        alert('Failed to save entry: ' + (j.message || 'unknown'));
      }
    } catch(e){
      console.error(e);
      alert('Network error while saving entry');
    }

  });

  // Expose a helper for serverless find endpoint - no exposure needed
  toggleSections();

  // Replace existing formatIST with this function
    function ordinal(n) {
      const s = ["th","st","nd","rd"],
            v = n % 100;
      return n + (s[(v-20)%10] || s[v] || s[0]);
    }

    function formatStoredTimestamp(utcString) {
      // Example input: "2025-11-27T19:24:15.619909+00:00" or "2025-11-27 19:24:15.619909+00"
      // Normalize to an ISO string JS Date accepts reliably
      let iso = utcString;
      if (typeof iso === 'string' && iso.indexOf('T') === -1 && iso.indexOf('+') !== -1) {
        // convert "YYYY-MM-DD HH:MM:SS.sss+00" -> "YYYY-MM-DDTHH:MM:SS.sss+00:00"
        iso = iso.replace(' ', 'T');
        // If timezone is +00 (no colon), ensure "+00:00"
        iso = iso.replace(/\+00$/, '+00:00');
      }

      const d = new Date(iso);
      if (isNaN(d.getTime())) return utcString; // fallback to raw string

      // We want to keep the instant as-is (Supabase UTC instant). Format it with timeZone:'UTC'
      const dd = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
      const dayNum = d.getUTCDate();
      // make ordinal like "27th Nov 2025"
      const dateWithOrdinal = `${ordinal(dayNum)} ${dd.split(' ').slice(1).join(' ')}`;

      const timeStr = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'UTC' });

      return `${dateWithOrdinal} - ${timeStr}`;
    }




  // Load today's entries into card list
    async function loadTodaysEntries() {
        try {
            const res = await fetch('/api/todays_entries');
            const entries = await res.json();
            const container = document.getElementById('todaysEntries');
            container.innerHTML = '';

            entries.forEach(e => {
                const card = document.createElement('div');
                card.className = 'card mb-2 shadow-sm';

                // FIX: define collapseId
                const collapseId = 'entry_' + Math.random().toString(36).substring(2, 8);

                const ts = formatStoredTimestamp(e.created_at);
                const parts = ts.split(' - ');
                const timePart = parts[1];
                const datePart = parts[0];

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
                                ${e.purpose_subtype ? ' (' + e.purpose_subtype + ')' : ''}
                            </div>
                        </div>
                    </div>

                    <div id="${collapseId}" class="collapse">
                        <div class="card-body">
                            <div style="font-size:0.95rem;"><strong>Type:</strong> ${e.entry_type || '-'}</div>
                            <div style="font-size:0.95rem;"><strong>Purpose:</strong> ${e.purpose_category || '-'}
                                ${e.purpose_subtype ? '(' + e.purpose_subtype + ')' : ''}
                            </div>
                            <div style="font-size:0.95rem;"><strong>Flat:</strong> ${e.flat_no || '-'}</div>
                        </div>
                    </div>
                `;

                container.appendChild(card);
            });

        } catch (err) {
            console.error('Load entries error:', err);
        }
    }

    // load immediately
    loadTodaysEntries();

    // reload after saving
//    setTimeout(() => loadTodaysEntries(), 400);

})();
