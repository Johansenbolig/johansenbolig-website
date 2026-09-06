// Henter indhold fra /content/*.json og indsætter det i siden.
// Ingen build-proces nødvendig: når CMS'et gemmer en ændring i en JSON-fil,
// vises den nye tekst/billede automatisk, næste gang siden indlæses.

async function loadContent(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error("Kunne ikke hente " + path);
  return res.json();
}

function el(tag, opts = {}) {
  const node = document.createElement(tag);
  if (opts.text) node.textContent = opts.text;
  if (opts.html) node.innerHTML = opts.html;
  if (opts.className) node.className = opts.className;
  if (opts.attrs) {
    for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, v);
  }
  return node;
}

async function renderHome() {
  const data = await loadContent("/content/home.json");

  document.getElementById("hero").style.backgroundImage = `url("${data.hero_image}")`;
  document.getElementById("hero-kicker").textContent = data.hero_kicker;
  document.getElementById("hero-title").textContent = data.hero_title;
  document.getElementById("property-name").textContent = data.property_name;
  document.getElementById("property-address").textContent = data.address;
  document.getElementById("status-heading").textContent = data.status_heading;
  document.getElementById("status-text").textContent = data.status_text;
  const statusEmail = document.getElementById("status-email");
  statusEmail.textContent = data.email;
  statusEmail.href = "mailto:" + data.email;
  document.getElementById("cta").textContent = data.cta_text;

  document.getElementById("intro-heading").textContent = data.intro_heading;
  const introText = document.getElementById("intro-text");
  introText.innerHTML = "";
  data.apartment_summaries.forEach((line) => {
    introText.appendChild(el("p", { text: line }));
  });

  document.getElementById("includes-heading").textContent = data.includes_heading;
  const includesList = document.getElementById("includes-list");
  includesList.innerHTML = "";
  data.includes.forEach((item) => {
    includesList.appendChild(el("li", { text: item }));
  });

  document.getElementById("listing-heading").textContent = data.listing_heading;
  const listingsWrap = document.getElementById("listings-wrap");
  listingsWrap.innerHTML = "";
  data.listings.forEach((listing) => {
    const block = el("div", { className: "listing" });
    block.appendChild(el("h3", { text: listing.title }));
    const grid = el("div", { className: "listing-grid" });
    listing.images.forEach((src) => {
      grid.appendChild(el("img", { attrs: { src, loading: "lazy", alt: listing.title } }));
    });
    block.appendChild(grid);
    listingsWrap.appendChild(block);
  });

  document.getElementById("footer-company").textContent = data.company_name;
  const footerEmail = document.getElementById("footer-email");
  footerEmail.textContent = data.email;
  footerEmail.href = "mailto:" + data.email;
  const footerAddress = document.getElementById("footer-address");
  footerAddress.innerHTML = data.footer_address_lines.join("<br>");
}

async function renderSimplePage(jsonPath) {
  const data = await loadContent(jsonPath);
  document.getElementById("page-heading").textContent = data.heading;

  if (data.body) {
    document.getElementById("page-body").textContent = data.body;
  }
  if (data.intro) {
    document.getElementById("page-body").textContent = data.intro;
  }

  const email = document.getElementById("page-email");
  if (email) {
    email.textContent = data.email;
    email.href = "mailto:" + data.email;
  }

  const addressBlock = document.getElementById("page-address");
  if (addressBlock && data.address_lines) {
    addressBlock.innerHTML = data.address_lines.join("<br>");
  }
}
