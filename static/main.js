document.addEventListener('DOMContentLoaded', function(){
  const leds = Array.from(document.querySelectorAll('.led'));
  const idToBtn = {};
  leds.forEach(b => idToBtn[b.dataset.ledId] = b);

  function setBtnState(btn, stateChar){
    btn.classList.remove('state-0','state-1','state-2');
    if(stateChar === '0') btn.classList.add('state-0');
    else if(stateChar === '1') btn.classList.add('state-1');
    else if(stateChar === '2') btn.classList.add('state-2');
    else btn.classList.add('state-0');
  }

  leds.forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.ledId;
      // toggle between off and on for simplicity
      const current = btn.classList.contains('state-1') ? '1' : (btn.classList.contains('state-2') ? '2' : '0');
      const next = current === '1' ? '0' : '1';
      const resp = await fetch('/api/led/set', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({id: id, ctrl: next})
      });
      const j = await resp.json();
      if(j.ok){
        setBtnState(btn, next);
      } else {
        addLog(`Failed to set LED ${id}`);
      }
    });
  });

  document.getElementById('req-leds').addEventListener('click', async () => {
    await fetch('/api/req/sta', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({which: 'LED'})});
  });

  document.getElementById('all-off').addEventListener('click', async () => {
    const resp = await fetch('/api/led/bulk', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({payload: '00000000'})
    });
    const j = await resp.json();
    if(!j.ok) addLog('Failed to turn off all LEDs');
  });

  // Amount calculation logic
  let totalAmount = 0;
  let productsData = []; // Store products for affordability check
  const totalAmountDisplay = document.getElementById('total-amount');
  const restockBtn = document.getElementById('restock-btn');
  
  async function updateVendingMachineLEDs() {
    // Update restock button state based on totalAmount
    if (totalAmount > 0) {
      restockBtn.disabled = true;
      restockBtn.style.opacity = "0.5";
      restockBtn.style.cursor = "not-allowed";
    } else {
      restockBtn.disabled = false;
      restockBtn.style.opacity = "1.0";
      restockBtn.style.cursor = "pointer";
    }

    if (productsData.length === 0) return;

    // Build 8-char payload: GRN0, GRN1, GRN2, GRN3, RED0, RED1, RED2, RED3
    let states = [];
    
    // Check first 4 products for GRN LEDs
    for (let i = 0; i < 4; i++) {
      // 条件: 投入金額 >= 価格 かつ 在庫 > 0
      if (productsData[i] && totalAmount >= productsData[i].price && productsData[i].stock > 0) {
        states.push("1"); // 条件を満たす：点灯
      } else {
        states.push("0"); // 条件を満たさない：消灯
      }
    }
    // RED LEDs (indices 4-7): 在庫切れの場合に点灯
    for (let i = 0; i < 4; i++) {
      if (productsData[i] && productsData[i].stock <= 0) {
        states.push("1"); // 在庫なし：赤点灯
      } else {
        states.push("0");
      }
    }

    const payload = states.join("");
    
    // UIの表示を即座に更新（レスポンス向上）
    const ids = ['GRN0','GRN1','GRN2','GRN3','RED0','RED1','RED2','RED3'];
    for(let i=0; i<8; i++) {
      const btn = idToBtn[ids[i]];
      if(btn) setBtnState(btn, states[i]);
    }

    try {
      await fetch('/api/led/bulk', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({payload: payload})
      });
    } catch (err) {
      console.error('Failed to update LEDs:', err);
    }
  }

  document.querySelectorAll('.coin').forEach(btn => {
    btn.addEventListener('click', async () => {
      const amount = parseInt(btn.dataset.amount);
      totalAmount += amount;
      totalAmountDisplay.textContent = totalAmount;
      addLog(`Added ${amount}円. Total: ${totalAmount}円`);
      await updateVendingMachineLEDs();
    });
  });

  document.getElementById('clear-amount').addEventListener('click', async () => {
    totalAmount = 0;
    totalAmountDisplay.textContent = totalAmount;
    addLog('Amount cleared');
    await updateVendingMachineLEDs();
  });

  document.getElementById('restock-btn').addEventListener('click', async () => {
    try {
      const resp = await fetch('/api/products/restock', { method: 'POST' });
      const j = await resp.json();
      if (j.ok) {
        productsData = j.products;
        renderProducts();
        addLog('All products restocked to capacity');
        await updateVendingMachineLEDs();
      }
    } catch (err) {
      console.error('Restock failed:', err);
      addLog('Restock failed');
    }
  });

  // Render products to the UI
  function renderProducts() {
    const productList = document.getElementById('product-list');
    productList.innerHTML = '';
    productsData.forEach(p => {
      const div = document.createElement('div');
      div.className = 'product-card';
      div.innerHTML = `
        <img src="${p.image_url}" alt="${p.name}" class="product-image">
        <div class="product-price">${p.price}円</div>
        <div class="product-name">${p.name}</div>
        <div class="product-stock">在庫: ${p.stock}</div>
      `;
      productList.appendChild(div);
    });
  }

  function playDispenseAnimation(product) {
    const overlay = document.getElementById('dispense-overlay');
    const img = document.getElementById('dispense-item');
    const msg = document.getElementById('dispense-msg');
    
    img.src = product.image_url;
    msg.textContent = `ガタン！ [${product.name}] を排出しました`;
    
    // Reset animation
    img.className = '';
    void img.offsetWidth; // trigger reflow
    img.className = 'dispense-animation';
    
    overlay.style.display = 'flex';
    
    setTimeout(() => {
      overlay.style.display = 'none';
    }, 2500);
  }

  // Handle product purchase
  async function purchaseProduct(index) {
    const product = productsData[index];
    if (!product) return;
    try {
      const resp = await fetch(`/api/products/${product.id}/purchase`, { method: 'POST' });
      const j = await resp.json();
      if (j.ok) {
        productsData[index] = j.product; // Update local data
        addLog(`Purchased: ${j.product.name}. Remaining stock: ${j.product.stock}`);
        
        playDispenseAnimation(j.product);
        
        renderProducts();
        await updateVendingMachineLEDs();
      }
    } catch (err) {
      console.error('Purchase failed:', err);
      addLog('Purchase failed');
    }
  }

  // Load product information from database
  async function loadProducts() {
    try {
      const resp = await fetch('/api/products');
      productsData = await resp.json();
      renderProducts();
      addLog('Products loaded from database');
      await updateVendingMachineLEDs();
    } catch (err) {
      console.error('Failed to load products:', err);
      addLog('Error loading products');
    }
  }

  loadProducts();

  // SSE listener
  const logDiv = document.getElementById('log');
  function addLog(msg){
    const div = document.createElement('div');
    div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logDiv.appendChild(div);
    logDiv.scrollTop = logDiv.scrollHeight;
  }

  const es = new EventSource('/stream');
  es.onmessage = function(e){
    try{
      const msg = JSON.parse(e.data);
      if(msg.type === 'LED' && typeof msg.payload === 'string' && msg.payload.length === 8){
        // mapping order: GRN0..GRN3, RED0..RED3
        const ids = ['GRN0','GRN1','GRN2','GRN3','RED0','RED1','RED2','RED3'];
        for(let i=0;i<8;i++){
          const id = ids[i];
          const b = idToBtn[id];
          if(b) setBtnState(b, msg.payload[i]);
        }
        addLog(`LED status updated: ${msg.payload}`);
      } else if(msg.type === 'NTF'){
        addLog(`Notification: ${msg.event} is ${msg.state}`);
        if(msg.state.toUpperCase() === 'OFF' && msg.event.startsWith('BTN')){
          const btnIdx = parseInt(msg.event.replace('BTN', ''));
          const product = productsData[btnIdx];
          if(product && totalAmount >= product.price && product.stock > 0){
            addLog(`Product [${product.name}] selected via ${msg.event}.`);
            totalAmount = 0;
            totalAmountDisplay.textContent = totalAmount;
            purchaseProduct(btnIdx);
          }
        }
      } else if(msg.type === 'BTN'){
        addLog(`Button snapshot: ${msg.payload}`);
      } else if(msg.type === 'ACK'){
        addLog(`ACK received: ${msg.cmd}`);
      } else if(msg.type === 'ERR'){
        addLog(`ERROR: ${msg.code} - ${msg.msg}`);
      } else {
        addLog(`Unknown/Raw message: ${JSON.stringify(msg)}`);
        console.log("Unknown msg type:", msg);
      }
    }catch(err){ console.error(err); }
  };
});