'use client';

import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function MapAL({ metrics, cargo, turno, selectedMunicipio, onSelectMunicipio }) {
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  useEffect(() => {
    if (mapRef.current) return;

    const map = L.map('map', { zoomControl: true }).setView([-9.66, -36.65], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap',
    }).addTo(map);

    mapRef.current = map;

    async function loadGeo() {
      const r = await fetch('/data/municipios_al.geojson', { cache: 'no-store' });
      const geo = await r.json();

      const layer = L.geoJSON(geo, {
        style: (feature) => {
          const cod = String(feature.properties?.CD_MUN || feature.properties?.cod_mun || feature.properties?.code_muni || feature.properties?.id || '');
          const m = metrics?.municipios?.[cod];
          const winner = m?.winner?.[cargo]?.[turno];
          const abst = m?.abst;
          const fillOpacity = selectedMunicipio && selectedMunicipio !== cod ? 0.25 : 0.65;
          // simple coloring by whether we have data + abst level
          let fillColor = '#1f2937';
          if (winner?.partido) fillColor = '#0ea5e9';
          if (abst !== null && abst !== undefined) {
            if (abst >= 0.25) fillColor = '#f59e0b';
            if (abst >= 0.35) fillColor = '#ef4444';
          }
          return { color: '#111827', weight: 1, fillColor, fillOpacity };
        },
        onEachFeature: (feature, lyr) => {
          const cod = String(feature.properties?.CD_MUN || feature.properties?.cod_mun || feature.properties?.code_muni || feature.properties?.id || '');
          const nome = feature.properties?.NM_MUN || feature.properties?.nome || feature.properties?.name || 'Município';
          const m = metrics?.municipios?.[cod];
          const w = m?.winner?.[cargo]?.[turno];
          const abst = m?.abst;

          lyr.bindTooltip(
            `<div style="font-size:12px"><b>${nome}</b><br/>Código: ${cod}<br/>Abstenção: ${abst!=null?(abst*100).toFixed(1)+'%':'—'}<br/>Vencedor: ${w?.nome || '—'} (${w?.partido || '—'})</div>`,
            { sticky: true }
          );

          lyr.on('click', () => onSelectMunicipio?.(cod));
        }
      }).addTo(map);

      layerRef.current = layer;
    }

    loadGeo();
  }, []);

  // restyle when filters change
  useEffect(() => {
    if (!layerRef.current) return;
    layerRef.current.setStyle((feature) => {
      const cod = String(feature.properties?.CD_MUN || feature.properties?.cod_mun || feature.properties?.code_muni || feature.properties?.id || '');
      const m = metrics?.municipios?.[cod];
      const winner = m?.winner?.[cargo]?.[turno];
      const abst = m?.abst;
      const fillOpacity = selectedMunicipio && selectedMunicipio !== cod ? 0.25 : 0.65;
      let fillColor = '#1f2937';
      if (winner?.partido) fillColor = '#0ea5e9';
      if (abst !== null && abst !== undefined) {
        if (abst >= 0.25) fillColor = '#f59e0b';
        if (abst >= 0.35) fillColor = '#ef4444';
      }
      return { color: '#111827', weight: 1, fillColor, fillOpacity };
    });
  }, [metrics, cargo, turno, selectedMunicipio]);

  return <div id="map" style={{ height: '100%', width: '100%' }} />;
}
