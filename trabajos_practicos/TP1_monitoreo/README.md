# Monitor de Procesos y Threads — TP1 Computación II

> Monitor del sistema en tiempo real estilo `htop`, que extrae la anatomía interna de cada
> proceso leyendo `/proc` directamente (sin `psutil`). Sistema multiproceso con TUI.

**Estado:** 🚧 en desarrollo — ver [plan.md](plan.md).

---

## Cómo correr

```bash
docker compose up --build
```

(requiere Docker; el monitor es Linux-only porque lee `/proc`).

---

## TODO del informe (se completa al final — es 15% de la nota)

- [ ] Descripción general
- [ ] Diagrama de arquitectura
- [ ] Decisiones de diseño (IPC elegido, Manager vs Value, race conditions, intervalos)
- [ ] Conceptos del curso aplicados (mapear código ↔ clases)
- [ ] Limitaciones conocidas
- [ ] Cómo correr y testear
- [ ] Capturas / GIF
- [ ] Lo que aprendí
