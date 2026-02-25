function transferScrapedData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const importSheet = ss.getSheetByName("Import");
  const uploadSheet = ss.getSheetByName("Upload");
  const worksheetSheet = ss.getSheetByName("Worksheet");

  if (!importSheet || !uploadSheet) {
    SpreadsheetApp.getUi().alert("Fehler: 'Import' oder 'Upload' Tabellenblatt fehlt.");
    return;
  }

  // --- 1. DATEN LADEN ---
  const importData = importSheet.getDataRange().getValues();
  if (importData.length < 2) {
    SpreadsheetApp.getUi().alert("Fehler: Import-Blatt ist leer.");
    return;
  }
  
  const importHeaders = importData[0].map(h => h.toString().trim().toLowerCase());
  const uploadHeaders = uploadSheet.getRange(1, 1, 1, uploadSheet.getLastColumn()).getValues()[0];
  const uploadHeadersNorm = uploadHeaders.map(h => h.toString().trim().toLowerCase());

  // --- 2. O2 AUS UPLOAD SICHERN ---
  let staticIntro = "";
  try {
    let rawO2 = uploadSheet.getRange("O2").getValue();
    if (rawO2) staticIntro = rawO2.toString().trim();
  } catch (e) { console.log(e); }

  // --- 3. SKU LOOKUP ---
  let skuMap = {}; 
  let worksheetLoaded = false;
  if (worksheetSheet) {
    const wData = worksheetSheet.getDataRange().getValues();
    if (wData.length > 1) {
      const wHeaders = wData[0].map(h => h.toString().trim().toLowerCase());
      let wPznIdx = -1, wSkuIdx = -1;
      
      const pznNames = ["pzn", "pzn text", "ean", "pharmazentralnummer"];
      for (let name of pznNames) if ((wPznIdx = wHeaders.indexOf(name)) > -1) break;

      const skuNames = ["sku", "artikelnummer", "art.nr.", "item no"];
      for (let name of skuNames) if ((wSkuIdx = wHeaders.indexOf(name)) > -1) break;

      if (wPznIdx > -1 && wSkuIdx > -1) {
        for (let i = 1; i < wData.length; i++) {
          let row = wData[i];
          let pznKey = row[wPznIdx].toString().trim();
          if (pznKey) skuMap[pznKey] = row[wSkuIdx].toString().trim();
        }
        worksheetLoaded = true;
      }
    }
  }

  // --- HELPER FUNKTIONEN ---
  const getSmartVal = (row, possibleNames) => {
    for (let name of possibleNames) {
      let idx = importHeaders.indexOf(name.toLowerCase());
      if (idx > -1) {
        let val = row[idx];
        return val ? val.toString().trim() : "";
      }
    }
    return "";
  };

  const getTargetIdx = (colName) => uploadHeadersNorm.indexOf(colName.toLowerCase());

  const cleanContent = (text, headerName) => {
    if (!text) return "";
    let clean = text.toString();

    // 1. Unsichtbare Zeichen entfernen
    clean = clean.replace(/[\u00A0\u1680\u180e\u2000-\u2009\u200a\u200b\u202f\u205f\u3000]/g, " ");
    clean = clean.trim();

    // 2. Zu kurz?
    if (clean.length < 2) return "";

    // 3. Ist der Text identisch mit der Überschrift? (Scraper-Fehler)
    if (headerName && clean.toLowerCase().replace(":", "").trim() === headerName.toLowerCase().replace(":", "").trim()) {
      return "";
    }
    
    // 4. Doppelpunkte am Ende entfernen
    clean = clean.replace(/:$/, "");

    return clean;
  };

  const formatText = (text) => {
    if (!text) return "";
    let clean = cleanContent(text, ""); 
    if (!clean) return "";

    clean = clean.replace(/([a-zäöüß])(\d)/g, "$1 $2");
    clean = clean.replace(/([a-zäöüß])([A-ZÄÖÜ])/g, "$1 $2");
    const units = "mg|g|µg|ml|l|IE|Stück|Kaps\\.|Tbl\\.|Drg\\.|Amp\\.|Pck\\.";
    const regexUnits = new RegExp(`(\\d+(?:[.,]\\d+)?\\s?(?:${units}))\\s?([A-ZÄÖÜ])`, "g");
    clean = clean.replace(regexUnits, "$1\n$2");
    return clean;
  };

  const formatAddress = (rawText) => {
    if (!rawText) return "";
    let text = rawText.toString();
    text = text.split(/(?:Kontaktdaten|Kontakt|Telefon|Tel\.|E-Mail|Email|Website|Fax)/i)[0].trim();
    text = text.replace(/([a-zäöüß])(Deutschland|Österreich|Schweiz)/gi, "$1 ($2)");
    if (!text.includes("(") && /(Deutschland|Österreich|Schweiz)$/i.test(text)) text = text.replace(/(Deutschland|Österreich|Schweiz)$/i, "($1)");
    const zipMatch = text.match(/(\d{5})/);
    if (zipMatch) {
      let zip = zipMatch[0];
      let parts = text.split(zip);
      let companyAndStreet = parts[0].trim();
      let cityAndCountry = parts.slice(1).join(zip).trim();
      companyAndStreet = companyAndStreet.replace(/(GmbH|AG|KG|SE|Co\.|Inc\.|e\.K\.|OHG)([A-ZÄÖÜ])/g, "$1, $2");
      if (!companyAndStreet.includes(",")) companyAndStreet = companyAndStreet.replace(/([a-zäöüß])([A-ZÄÖÜ])/g, "$1, $2");
      text = `${companyAndStreet}, ${zip} ${cityAndCountry}`;
    }
    return text.replace(/\s+/g, " ").replace(/,\s*,/g, ",").trim();
  };

  // --- HAUPTSCHLEIFE ---
  const importRows = importData.slice(1);
  const newRows = importRows.map(row => {
    let outputRow = new Array(uploadHeaders.length).fill("");

    // 1. NAME
    let nameVal = getSmartVal(row, ["Name", "Produktname", "Artikelbezeichnung"]);
    let idxName = getTargetIdx("Names");
    if (idxName === -1) idxName = getTargetIdx("Name");
    if (idxName > -1) outputRow[idxName] = nameVal;

    // MENGE & UOM
    let amount = "1";
    let uom = "Stk.";
    if (nameVal) {
      let matchVol = nameVal.match(/(\d+(?:[.,]\d+)?)\s*(ml|l|liter)\b/i);
      let matchWeight = nameVal.match(/(\d+(?:[.,]\d+)?)\s*(g|gr|gramm|kg)\b/i);
      if (matchVol) {
        let val = parseFloat(matchVol[1].replace(",", "."));
        if (matchVol[2].toLowerCase() === "ml") val = val / 1000;
        amount = val.toString();
        uom = "l";
      } else if (matchWeight) {
        let val = parseFloat(matchWeight[1].replace(",", "."));
        let unit = matchWeight[2].toLowerCase();
        if (["g", "gr", "gramm"].includes(unit)) val = val / 1000;
        amount = val.toString();
        uom = "kg";
      } else {
        let matchCount = nameVal.match(/(\d+)\s*(?:St|Stk|Stück|Tbl|Tabletten|Kaps|Kapseln|Drg|Dragees|Amp|Ampullen|Btl|Beutel|Pflaster)/i);
        if (matchCount) {
          amount = matchCount[1];
          uom = "Stk.";
        }
      }
    }
    
    let idxUnit = getTargetIdx("productUnit");
    if (idxUnit > -1) outputRow[idxUnit] = amount;
    let idxUom = getTargetIdx("uom");
    if (idxUom > -1) outputRow[idxUom] = uom;
    let idxBase = getTargetIdx("baseUnit");
    if (idxBase > -1) outputRow[idxBase] = "1";

    // PZN & SKU
    let pzn = getSmartVal(row, ["PZN", "Artikelnummer", "PZN Text"]);
    let idxPzn = getTargetIdx("PZN");
    if (idxPzn > -1) outputRow[idxPzn] = pzn;

    if (pzn && worksheetLoaded && skuMap[pzn]) {
      let idxSku = getTargetIdx("sku");
      if (idxSku > -1) outputRow[idxSku] = skuMap[pzn];
    }

    // STORAGE
    let idxStorage = getTargetIdx("storage");
    if (idxStorage > -1) outputRow[idxStorage] = "Bitte trocken und vor Wärme geschützt lagern. Außerhalb der Reichweite von Kindern lagern.";

    // INGREDIENTS
    let wirk = formatText(getSmartVal(row, ["Wirkstoffe", "Wirkstoffe Text", "Wirkstoff"]));
    let idxIng = getTargetIdx("ingredients");
    if (idxIng > -1) outputRow[idxIng] = wirk;

    // --- DESCRIPTION ZUSAMMENBAUEN ---
    let descParts = [];

    // 0. Intro aus O2
    if (staticIntro) descParts.push(staticIntro);

    // 1. Technische Beschreibung (OHNE Überschrift)
    let techRaw = getSmartVal(row, ["Technische Beschreibung", "Technische Beschreibung Text", "Technische Daten"]);
    let tech = formatText(techRaw);
    if (cleanContent(techRaw, "Technische Beschreibung")) {
        descParts.push(tech);
    }

    // 2. Hilfsstoffe
    let hilfsRaw = getSmartVal(row, ["Hilfsstoffe", "Hilfsstoffe Text", "Inhaltsstoffe"]);
    if (cleanContent(hilfsRaw, "Hilfsstoffe")) {
        descParts.push("Hilfsstoffe:\n" + formatText(hilfsRaw));
    }
    
    // 3. Dosierung
    let dosRaw = getSmartVal(row, ["Dosierung", "Dosierung Text"]);
    if (cleanContent(dosRaw, "Dosierung")) {
        descParts.push("Dosierung:\n" + formatText(dosRaw));
    }

    // 4. Patientenhinweise
    let patRaw = getSmartVal(row, ["Patientenhinweise", "Patientenhinweise Text"]);
    if (cleanContent(patRaw, "Patientenhinweise")) {
        descParts.push("Patientenhinweise:\n" + formatText(patRaw));
    }
    
    // 5. Warnhinweise (Neu im Scraper)
    let warnRaw = getSmartVal(row, ["Warnhinweise", "Warnhinweise Text"]);
    if (cleanContent(warnRaw, "Warnhinweise")) {
        descParts.push("Warnhinweise:\n" + formatText(warnRaw));
    }

    // 6. Anwendungshinweise
    let anwRaw = getSmartVal(row, ["Anwendungshinweise", "Anwendungshinweise Text"]);
    if (cleanContent(anwRaw, "Anwendungshinweise")) {
        descParts.push("Anwendungshinweise:\n" + formatText(anwRaw));
    }
    
    // 7. Wechselwirkungen (Aus dem neuen Scraper)
    let wechsRaw = getSmartVal(row, ["Wechselwirkungen", "Wechselwirkung", "Wechselwirkungen Text"]);
    if (cleanContent(wechsRaw, "Wechselwirkungen")) {
        descParts.push("Wechselwirkungen:\n" + formatText(wechsRaw));
    }

    // 8. Stillzeit
    let stillRaw = getSmartVal(row, ["Stillzeit", "Stillzeit Text", "Schwangerschaft"]);
    if (cleanContent(stillRaw, "Stillzeit")) {
        descParts.push("Stillzeit:\n" + formatText(stillRaw));
    }

    // 9. Produktbeschreibung
    let prodRaw = getSmartVal(row, ["Produktbeschreibung", "Produktbeschreibung Text"]);
    if (cleanContent(prodRaw, "Produktbeschreibung")) {
        descParts.push("Produktbeschreibung:\n" + formatText(prodRaw));
    }

    // 10. Produkteigenschaften
    let propRaw = getSmartVal(row, ["Produkteigenschaften", "Produkteigenschaften Text"]);
    if (cleanContent(propRaw, "Produkteigenschaften")) {
        descParts.push("Produkteigenschaften:\n" + formatText(propRaw));
    }

    let idxDesc = getTargetIdx("description");
    if (idxDesc > -1) outputRow[idxDesc] = descParts.join("\n\n");

    // OTHER FIELDS
    let anwGeb = formatText(getSmartVal(row, ["Anwendungsgebiete", "Anwendungsgebiete Text"]));
    let idxField = getTargetIdx("fieldOfApplication");
    if (idxField > -1) outputRow[idxField] = anwGeb;

    let nebenRaw = getSmartVal(row, ["Nebenwirkungen", "Nebenwirkungen Text"]);
    let neben = formatText(nebenRaw);
    if (!cleanContent(nebenRaw, "Nebenwirkungen")) {
        neben = "Zu Risiken und Nebenwirkungen lesen Sie die Packungsbeilage und fragen Sie Ihre Ärztin, Ihren Arzt oder in Ihrer Apotheke";
    }
    let idxSide = getTargetIdx("sideEffects");
    if (idxSide === -1) idxSide = getTargetIdx("global_sideEffects");
    if (idxSide > -1) outputRow[idxSide] = neben;

    let gegenRaw = getSmartVal(row, ["Gegenanzeigen", "Gegenanzeigen Text"]);
    if (cleanContent(gegenRaw, "Gegenanzeigen")) {
        let idxAll = getTargetIdx("allergens");
        if (idxAll > -1) outputRow[idxAll] = "Gegenanzeigen:\n" + formatText(gegenRaw);
    }

    // >>> NEU: PRODUCER (HERSTELLER + ADRESSE) <<<
    let herstRaw = getSmartVal(row, ["Hersteller", "Hersteller Text", "Anbieter"]);
    let adrRaw = getSmartVal(row, ["Adresse", "Adresse Text"]);
    
    let combinedHersteller = herstRaw;
    if (adrRaw && adrRaw.length > 0) {
      // Wenn der Hersteller schon da ist, mit Komma anhängen, sonst nur Adresse nehmen
      combinedHersteller = combinedHersteller ? (combinedHersteller + ", " + adrRaw) : adrRaw;
    }

    let herstClean = formatAddress(combinedHersteller);
    let idxProd = getTargetIdx("producer");
    if (idxProd > -1) outputRow[idxProd] = herstClean;
    let idxHerst = getTargetIdx("Hersteller");
    if (idxHerst > -1) outputRow[idxHerst] = herstClean;

    return outputRow;
  });

  // --- SCHREIBEN ---
  if (newRows.length > 0) {
    if (uploadSheet.getLastRow() > 1) uploadSheet.getRange(2, 1, uploadSheet.getLastRow()-1, uploadSheet.getLastColumn()).clearContent();
    uploadSheet.getRange(2, 1, newRows.length, newRows[0].length).setValues(newRows);
    SpreadsheetApp.getUi().alert("Erfolg: Neues Scraper-Format übernommen ('Hersteller' + 'Adresse' kombiniert & neue Felder integriert).");
  }
}
