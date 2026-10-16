// PartnerWAV alerts on this device. The portal sends each alert through here, because phone browsers only
// show notifications from a service worker. Nothing is cached and nothing is fetched by this file.
self.addEventListener("install", function(){ self.skipWaiting(); });
self.addEventListener("activate", function(e){ e.waitUntil(self.clients.claim()); });

// Tapping an alert opens the portal (or brings its open window forward) and shows that notification.
self.addEventListener("notificationclick", function(e){
  e.notification.close();
  var id = (e.notification.data && e.notification.data.id) || "";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function(list){
    for (var i = 0; i < list.length; i++){
      if ("focus" in list[i]){ list[i].postMessage({ type: "open", id: id }); return list[i].focus(); }
    }
    return self.clients.openWindow(self.registration.scope + "partnerwav-v11-merged.html").then(function(w){
      if (w) setTimeout(function(){ w.postMessage({ type: "open", id: id }); }, 1500);
    });
  }));
});
