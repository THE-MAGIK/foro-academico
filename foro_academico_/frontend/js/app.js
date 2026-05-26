const { createApp } = Vue;

/**
 * Prefijo API: vacío en Vite/preview (rutas /api con proxy → Flask) para que la
 * cookie de sesión sea del mismo sitio que la página (evita "No autenticado"
 * si entras por localhost:5173 y antes llamabas a 127.0.0.1:3000).
 */
const API = (() => {
  if (typeof window === 'undefined') return 'http://127.0.0.1:3000';
  const h = window.location.hostname;
  const p = String(window.location.port || '');
  if (
    (h === 'localhost' || h === '127.0.0.1') &&
    ['5173', '5174', '4173', '4174', '5500'].includes(p)
  ) {
    return '';
  }
  // Mismo host que la página (evita cookies huérfanas localhost vs 127.0.0.1)
  if (h === 'localhost' || h === '127.0.0.1') {
    return `http://${h}:3000`;
  }
  return 'http://127.0.0.1:3000';
})();

/** Textos de interfaz (español) traducibles con la API cuando está activa la traducción global. */
const TEXTOS_UI = {
  nav_brand: 'Foro académico',
  nav_buscar: 'Buscar preguntas…',
  nav_salir: 'Salir',
  menu_titulo: 'Menú',
  menu_inicio: 'Inicio',
  menu_historial: 'Historial',
  menu_pregunta: 'Haz pregunta',
  menu_etiquetas: 'Etiquetas',
  menu_aula: 'Aula (tareas)',
  menu_usuarios: 'Usuarios (supremo)',
  menu_perfil: 'Editar perfil',
  preguntas_titulo: 'Preguntas',
  preguntas_sub: 'Foro de dudas y debate',
  filtrar_ph: 'Filtrar por etiqueta (ej: python)',
  filtrar_btn: 'Filtrar',
  traducir_a: 'Traducir todo a:',
  traduciendo: 'Traduciendo…',
  ver_originales: 'Ver originales',
  traducir_todo: 'Traducir todo',
  mostrando_trad: 'Mostrando traducción al',
  pagina_actual: '(página actual)',
  sin_preguntas: 'No hay preguntas para mostrar.',
  score: 'Score:',
  ya_votaste: 'Ya votaste',
  voto_pos: 'positivo',
  voto_neg: 'negativo',
  respuestas: 'Respuestas',
  sin_respuestas: 'Aún no hay respuestas.',
  ya_votaste_corto: 'Ya votaste.',
  comentarios: 'Comentarios',
  comentario_ph: 'Escribe un comentario',
  comentar: 'Comentar',
  cancelar: 'Cancelar',
  responder: 'Responder',
  respuesta_ph: 'Escribe tu respuesta',
  publicar_respuesta: 'Publicar respuesta',
  anterior: 'Anterior',
  siguiente: 'Siguiente',
  pagina: 'Página',
  de: 'de',
  usuario: 'Usuario',
  hist_titulo: 'Historial de preguntas',
  hist_sub_est: 'Preguntas que has publicado en el foro, de la más reciente a la más antigua.',
  hist_sub_all: 'Todas las preguntas creadas en el foro, de la más reciente a la más antigua.',
  hist_vacio_est: 'Aún no has publicado ninguna pregunta.',
  hist_vacio_all: 'No hay preguntas registradas en el foro.',
  ver_en_foro: 'Ver en el foro',
};

createApp({
  data(){
    return {
      pantalla:'inicio',
      vista:'inicio',
      mensaje:'',
      busqueda:'',
      email:'',
      password:'',
      nueva:{ titulo:'', descripcion:'', tagsSeleccionados: [] },
      tagsCatalogo: [],
      tagBorrador: '',
      moderacionTagNueva: '',
      contacto:{nombre:'',mensaje:''},
      perfilForm:{nombre:'',email:'',password:''},
      perfilAvatarFile: null,
      perfilAvatarPreview: null,
      avatarCacheBust: 0,
      preguntas:[],
      historialPreguntas: [],
      historialPage: 1,
      historialTotalPages: 1,
      historialPerPage: 5,
      historialScope: 'all',
      idiomaTraduccion: 'en',
      traduccionGlobalActiva: false,
      traduccionGlobalCargando: false,
      traduccionesPreguntas: {},
      traduccionesRespuestas: {},
      traduccionesComentarios: {},
      traduccionesUI: {},
      currentUser: null,
      respuestasPorPregunta: {},
      comentariosPorPregunta: {},
      comentarioDraft: {},
      votosPreguntas: {},
      votosRespuestas: {},
      respondiendoPreguntaId: null,
      borradorRespuesta: '',
      page: 1,
      perPage: 5,
      totalPages: 1,
      filtroTag: '',
      usuariosGlobales: [],
      superUsuarioFormActivo: false,
      superEsCreacion: false,
      superEdit: { id: null, nombre: '', email: '', password: '', rol: 'estudiante' },
      aulaTareas: [],
      aulaNueva: { titulo: '', descripcion: '', fecha_entrega: '' },
      aulaEntregasDe: null,
      aulaEntregasEsModeracion: false,
      aulaEntregasLista: [],
      aulaComentariosPorTarea: {},
      aulaComentarioDraft: {},
      aulaGradesDraft: {},
      aulaReplyParentId: null,
      aulaReplyAssignmentId: null,
      aulaEstudianteBorrador: {},
      loginDiagnostico: null,
      appModal: {
        visible: false,
        tipo: 'alert',
        titulo: 'Aviso',
        mensaje: '',
        okText: 'Aceptar',
        cancelText: 'Cancelar',
        okDanger: false,
        promptValor: '',
        _resolve: null,
        _resolvePrompt: null
      }
    }
  },

  computed:{
    esEstudiante(){
      return this.currentUser && this.currentUser.rol === 'estudiante';
    },
    esProfesor(){
      return this.currentUser && this.currentUser.rol === 'profesor';
    },
    esModerador(){
      return this.currentUser && (this.currentUser.rol === 'admin' || this.currentUser.rol === 'superadmin');
    },
    esSuperAdmin(){
      return this.currentUser && this.currentUser.rol === 'superadmin';
    },
    esProfesorEnAula(){
      return this.esProfesor || this.esSuperAdmin;
    },
    esEstudianteEnAula(){
      return this.esEstudiante || this.esSuperAdmin;
    },
    loginCorreoValido(){
      return this.esCorreoValido(this.email);
    },
    loginBotonHabilitado(){
      return this.loginCorreoValido;
    },
    loginDiagnosticoTitulo(){
      return this.tituloDiagnostico(this.loginDiagnostico?.regla);
    },
    historialSubtitulo(){
      return this.textoUI(this.esEstudiante ? 'hist_sub_est' : 'hist_sub_all');
    },
    historialVacio(){
      return this.textoUI(this.esEstudiante ? 'hist_vacio_est' : 'hist_vacio_all');
    },
  },

  watch: {
    busqueda() {
      clearTimeout(this._debounceBusqueda);
      this._debounceBusqueda = setTimeout(() => {
        this.cargarPreguntas(1);
      }, 400);
    },
    vista(v){
      if(v === 'pregunta' && this.esEstudiante){
        this.cargarTagsCatalogo();
      }
    },
    idiomaTraduccion(){
      this.reiniciarTraducciones();
    },
    pantalla(p){
      if(p === 'login'){
        this.loginDiagnostico = null;
      }
    },
  },

  mounted(){
    this._onAppKeydown = e=>{
      if(e.key === 'Escape' && this.appModal.visible){
        this.modalCancelar();
      }
    };
    document.addEventListener('keydown', this._onAppKeydown);
  },

  beforeUnmount(){
    if(this._onAppKeydown){
      document.removeEventListener('keydown', this._onAppKeydown);
    }
  },

  methods:{

    tituloDiagnostico(regla){
      const map = {
        modus_tollens: 'Credenciales incorrectas (Modus Tollens)',
        modus_ponens: 'Acceso correcto (Modus Ponens)',
        validacion: 'Validación de entrada',
        servidor_no_disponible: 'No es por credenciales — el servidor no respondió',
      };
      return map[regla] || 'Diagnóstico lógico';
    },

    diagnosticoServidorCaido(detalle){
      return {
        regla: 'servidor_no_disponible',
        premisa_1: (
          'P → Q: Si el servidor de login responde, obtienes JSON '
          + '(éxito o rechazo por credenciales con diagnóstico).'
        ),
        premisa_2: (
          '¬Q: No hubo respuesta válida del API'
          + (detalle ? ` (${detalle})` : '')
          + ' — no se pudo comprobar tu correo en la base de datos.'
        ),
        conclusion: (
          '∴ NO es un fallo de credenciales: el problema es de infraestructura '
          + '(Flask parado, error al arrancar, MySQL apagado o sin conexión).'
        ),
      };
    },

    diagnosticoMysqlCaido(detalle){
      return {
        regla: 'servidor_no_disponible',
        premisa_1: (
          'P → Q: Si Flask y MySQL responden, /api/health indica db: true '
          + 'y el login puede validar credenciales.'
        ),
        premisa_2: (
          '¬Q: Flask responde, pero MySQL no conecta'
          + (detalle ? ` (${detalle})` : '')
          + ' — no se puede consultar la base de datos.'
        ),
        conclusion: (
          '∴ NO es conclusión segura sobre tu contraseña: '
          + 'falla la capa de datos (servicio MySQL o configuración en db.py).'
        ),
      };
    },

    esCorreoValido(correo){
      const c = (correo || '').trim();
      return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/i.test(c);
    },

    mostrarAviso(mensaje, titulo = 'Aviso'){
      this.appModal.tipo = 'alert';
      this.appModal.titulo = titulo;
      this.appModal.mensaje = mensaje == null ? '' : String(mensaje);
      this.appModal.okText = 'Aceptar';
      this.appModal.cancelText = '';
      this.appModal.okDanger = false;
      this.appModal.promptValor = '';
      this.appModal._resolve = null;
      this.appModal._resolvePrompt = null;
      this.appModal.visible = true;
    },

    confirmarAsync(mensaje, titulo = 'Confirmar', okText = 'Aceptar', cancelText = 'Cancelar', opts = {}){
      return new Promise(resolve=>{
        this.appModal.tipo = 'confirm';
        this.appModal.titulo = titulo;
        this.appModal.mensaje = mensaje == null ? '' : String(mensaje);
        this.appModal.okText = okText;
        this.appModal.cancelText = cancelText;
        this.appModal.okDanger = !!opts.danger;
        this.appModal.promptValor = '';
        this.appModal._resolvePrompt = null;
        this.appModal._resolve = resolve;
        this.appModal.visible = true;
      });
    },

    promptTextoAsync(mensaje, valorInicial = '', titulo = 'Entrada'){
      return new Promise(resolve=>{
        this.appModal.tipo = 'prompt';
        this.appModal.titulo = titulo;
        this.appModal.mensaje = mensaje == null ? '' : String(mensaje);
        this.appModal.okText = 'Aceptar';
        this.appModal.cancelText = 'Cancelar';
        this.appModal.okDanger = false;
        this.appModal.promptValor = valorInicial == null ? '' : String(valorInicial);
        this.appModal._resolve = null;
        this.appModal._resolvePrompt = resolve;
        this.appModal.visible = true;
      });
    },

    modalAceptar(){
      if(this.appModal.tipo === 'prompt' && this.appModal._resolvePrompt){
        const v = this.appModal.promptValor;
        this.appModal._resolvePrompt(v);
        this.appModal._resolvePrompt = null;
        this.appModal.visible = false;
        return;
      }
      if(this.appModal._resolve){
        this.appModal._resolve(true);
        this.appModal._resolve = null;
      }
      this.appModal.visible = false;
    },

    modalCancelar(){
      if(this.appModal.tipo === 'prompt' && this.appModal._resolvePrompt){
        this.appModal._resolvePrompt(null);
        this.appModal._resolvePrompt = null;
        this.appModal.visible = false;
        return;
      }
      if(this.appModal._resolve){
        this.appModal._resolve(false);
        this.appModal._resolve = null;
      }
      this.appModal.visible = false;
    },

    async comprobarServidorDisponible(){
      const controlador = new AbortController();
      const timeoutId = setTimeout(() => controlador.abort(), 5000);
      try{
        const res = await fetch(`${API}/api/health?_=${Date.now()}`, {
          method: 'GET',
          credentials: 'include',
          cache: 'no-store',
          headers: { 'Cache-Control': 'no-cache', Pragma: 'no-cache' },
          signal: controlador.signal,
        });
        const tipoJson = (res.headers.get('content-type') || '').includes('application/json');
        if(!res.ok || !tipoJson){
          return { listo: false, tipo: 'api' };
        }
        const data = await res.json();
        if(!data || data.api !== true || data.servicio !== 'foro-academico'){
          return { listo: false, tipo: 'api' };
        }
        if(data.db === false){
          return { listo: false, tipo: 'db', error: data.db_error || '' };
        }
        return { listo: true };
      }catch{
        return { listo: false, tipo: 'api' };
      }finally{
        clearTimeout(timeoutId);
      }
    },

    //  LOGIN REAL: primero /api/health, luego /api/login (no confundir caido vs credenciales)
    async login(){
      if(!this.loginBotonHabilitado){
        return;
      }
      this.loginDiagnostico = null;

      const check = await this.comprobarServidorDisponible();
      if(!check.listo){
        this.loginDiagnostico = check.tipo === 'db'
          ? this.diagnosticoMysqlCaido(check.error)
          : this.diagnosticoServidorCaido();
        return;
      }

      try{
        const res = await fetch(`${API}/api/login`,{
          method:'POST',
          credentials:'include',
          headers:{
            'Content-Type':'application/json'
          },
          body: JSON.stringify({
            email: (this.email || '').trim(),
            password: this.password
          })
        });

        const tipoJson = (res.headers.get('content-type') || '').includes('application/json');
        let data = {};
        if(tipoJson){
          try{
            data = await res.json();
          }catch{
            data = {};
          }
        }

        if(data.success && data.user){
          this.loginDiagnostico = null;
          this.currentUser = data.user;
          this.pantalla='foro';
          this.vista='inicio';
          this.mensaje = `Bienvenido, ${data.user.nombre} (${data.user.rol})`;
          this.cargarPreguntas();
          return;
        }

        if(res.status === 401 && data.diagnostico){
          this.loginDiagnostico = data.diagnostico;
          return;
        }

        if(data.diagnostico){
          this.loginDiagnostico = data.diagnostico;
          return;
        }

        this.loginDiagnostico = this.diagnosticoServidorCaido();
      }catch{
        this.loginDiagnostico = this.diagnosticoServidorCaido();
      }
    },

    irHistorial(){
      this.vista = 'historial';
      this.cargarHistorialPreguntas(1);
    },

    cargarHistorialPreguntas(page = this.historialPage){
      this.historialPage = page;
      const params = new URLSearchParams({
        page: String(this.historialPage),
        per_page: String(this.historialPerPage),
      });
      fetch(`${API}/api/questions/history?${params.toString()}`, { credentials: 'include' })
        .then(async res=>{
          const data = await res.json().catch(()=>({}));
          if(!res.ok){
            throw new Error(data.error || `Error al cargar historial (${res.status})`);
          }
          return data;
        })
        .then(data=>{
          this.historialPreguntas = data.items || [];
          this.historialTotalPages = Math.max(data.total_pages || 1, 1);
          this.historialScope = data.scope || 'all';
        })
        .catch(err=>{
          this.mostrarAviso(err.message || 'No se pudo cargar el historial');
          this.historialPreguntas = [];
          this.historialTotalPages = 1;
        });
    },

    verPreguntaEnInicio(questionId){
      this.vista = 'inicio';
      this.busqueda = '';
      this.filtroTag = '';
      this.page = 1;
      const params = new URLSearchParams({
        page: '1',
        per_page: String(this.perPage),
        id: String(questionId),
      });
      fetch(`${API}/api/questions?${params.toString()}`)
        .then(async res=>{
          const data = await res.json().catch(()=>({}));
          if(!res.ok){
            throw new Error(data.error || 'No se pudo abrir la pregunta');
          }
          return data;
        })
        .then(data=>{
          this.preguntas = data.items || [];
          this.totalPages = data.total_pages || 1;
          this.reiniciarTraducciones();
          this.cargarRespuestasDePreguntas();
          this.cargarComentariosDePreguntas();
          this.cargarVotosPreguntas();
          this.$nextTick(()=>{
            const el = document.getElementById(`pregunta-${questionId}`);
            if(el){
              el.scrollIntoView({ behavior: 'smooth', block: 'start' });
              el.classList.add('question-card--highlight');
              setTimeout(()=> el.classList.remove('question-card--highlight'), 2500);
            }
          });
        })
        .catch(err=> this.mostrarAviso(err.message));
    },

    //  TRAER PREGUNTAS DESDE MYSQL
    cargarPreguntas(page = this.page){
      this.page = page;
      const params = new URLSearchParams({
        page: String(this.page),
        per_page: String(this.perPage),
        q: this.busqueda || ''
      });
      if(this.filtroTag){
        params.set('tag', this.filtroTag);
      }

      return fetch(`${API}/api/questions?${params.toString()}`)
      .then(async res=>{
        const data = await res.json().catch(()=>({}));
        if(!res.ok){
          throw new Error(data.error || `Error al cargar preguntas (${res.status})`);
        }
        return data;
      })
      .then(data=>{
        this.preguntas = data.items || [];
        this.totalPages = data.total_pages || 1;
        this.reiniciarTraducciones();
        this.cargarRespuestasDePreguntas();
        this.cargarComentariosDePreguntas();
        this.cargarVotosPreguntas();
        return data;
      })
      .catch(err=>{
        console.error(err);
        this.mostrarAviso(err.message || 'No se pudieron cargar las preguntas');
        this.preguntas = [];
        this.totalPages = 1;
        throw err;
      });
    },

    cargarRespuestasDePreguntas(){
      this.preguntas.forEach(pregunta=>{
        fetch(`${API}/api/questions/${pregunta.id}/answers`)
        .then(res=>res.json())
        .then(data=>{
          this.respuestasPorPregunta[pregunta.id] = data;
          (data || []).forEach(respuesta => this.cargarVotosRespuesta(respuesta.id));
        })
        .catch(()=>{
          this.respuestasPorPregunta[pregunta.id] = [];
        });
      });
    },

    cargarComentariosDePreguntas(){
      this.preguntas.forEach(pregunta=>{
        fetch(`${API}/api/questions/${pregunta.id}/comments`)
        .then(res=>res.json())
        .then(data=>{
          this.comentariosPorPregunta[pregunta.id] = data;
        })
        .catch(()=>{
          this.comentariosPorPregunta[pregunta.id] = [];
        });
      });
    },

    cargarVotosPreguntas(){
      const uid = this.currentUser && this.currentUser.id;
      this.preguntas.forEach(pregunta=>{
        let url = `${API}/api/questions/${pregunta.id}/votes`;
        if(uid){
          url += `?user_id=${encodeURIComponent(String(uid))}`;
        }
        fetch(url)
        .then(res=>res.json())
        .then(data=>{ this.votosPreguntas[pregunta.id] = data; })
        .catch(()=>{ this.votosPreguntas[pregunta.id] = { score: 0 }; });
      });
    },

    cargarVotosRespuesta(answerId){
      const uid = this.currentUser && this.currentUser.id;
      let url = `${API}/api/answers/${answerId}/votes`;
      if(uid){
        url += `?user_id=${encodeURIComponent(String(uid))}`;
      }
      fetch(url)
      .then(res=>res.json())
      .then(data=>{ this.votosRespuestas[answerId] = data; })
      .catch(()=>{ this.votosRespuestas[answerId] = { score: 0 }; });
    },

    irNuevaPregunta(){
      this.vista = 'pregunta';
      this.nueva = { titulo: '', descripcion: '', tagsSeleccionados: [] };
      this.tagBorrador = '';
      this.cargarTagsCatalogo();
    },

    cargarTagsCatalogo(){
      fetch(`${API}/api/tags`, { credentials: 'include' })
        .then(r=>r.json())
        .then(rows=>{
          this.tagsCatalogo = Array.isArray(rows) ? rows : [];
        })
        .catch(()=>{ this.tagsCatalogo = []; });
    },

    toggleTagSeleccion(nombre){
      const n = String(nombre || '').trim().toLowerCase();
      if(!n){ return; }
      const i = this.nueva.tagsSeleccionados.indexOf(n);
      if(i >= 0){
        this.nueva.tagsSeleccionados.splice(i, 1);
      } else {
        this.nueva.tagsSeleccionados.push(n);
      }
    },

    quitarTagSel(nombre){
      const n = String(nombre || '').trim().toLowerCase();
      const i = this.nueva.tagsSeleccionados.indexOf(n);
      if(i >= 0){
        this.nueva.tagsSeleccionados.splice(i, 1);
      }
    },

    anadirTagPersonalizada(){
      const raw = (this.tagBorrador || '').trim();
      if(!raw){
        return;
      }
      raw.split(',').forEach(part=>{
        const t = part.trim().toLowerCase();
        if(t && !this.nueva.tagsSeleccionados.includes(t)){
          this.nueva.tagsSeleccionados.push(t);
        }
      });
      this.tagBorrador = '';
    },

    guardarNuevoTagModerador(){
      if(!this.esModerador){
        return;
      }
      const nombre = (this.moderacionTagNueva || '').trim().toLowerCase();
      if(!nombre){
        return this.mostrarAviso('Escribe un nombre de etiqueta');
      }
      fetch(`${API}/api/tags`,{
        method:'POST',
        credentials:'include',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ nombre })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo crear');
        }
        return data;
      })
      .then(()=>{
        this.moderacionTagNueva = '';
        this.mostrarAviso('Etiqueta creada');
        this.cargarTagsCatalogo();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async renombrarTagModer(t){
      if(!this.esModerador){
        return;
      }
      const actual = await this.promptTextoAsync('Nuevo nombre de la etiqueta', t.nombre, 'Renombrar etiqueta');
      if(actual == null){
        return;
      }
      const nombre = String(actual).trim().toLowerCase();
      if(!nombre){
        return this.mostrarAviso('Nombre vacío');
      }
      fetch(`${API}/api/tags/${t.id}`,{
        method:'PATCH',
        credentials:'include',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ nombre })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo actualizar');
        }
        return data;
      })
      .then(()=>{
        this.mostrarAviso('Etiqueta actualizada');
        this.cargarTagsCatalogo();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async eliminarTagModer(t){
      if(!this.esModerador){
        return;
      }
      if(!(await this.confirmarAsync(`¿Eliminar la etiqueta «${t.nombre}»? Se quitará de todas las preguntas donde esté asignada.`, 'Eliminar etiqueta', 'Eliminar', 'Cancelar', { danger: true }))){
        return;
      }
      fetch(`${API}/api/tags/${t.id}`,{
        method:'DELETE',
        credentials:'include'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo eliminar');
        }
        return data;
      })
      .then(()=>{
        this.mostrarAviso('Etiqueta eliminada');
        this.cargarTagsCatalogo();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    // CREAR PREGUNTA EN BD
    agregarPregunta(){
      if(!this.currentUser){
        return this.mostrarAviso('Debes iniciar sesión');
      }

      if(!this.esEstudiante){
        return this.mostrarAviso('Solo estudiantes pueden publicar preguntas');
      }

      if(!this.nueva.titulo || !this.nueva.descripcion){
        return this.mostrarAviso('Completa título y descripción');
      }

      fetch(`${API}/api/questions`,{
        method:'POST',
        headers:{
          'Content-Type':'application/json'
        },
        body: JSON.stringify({
          titulo: this.nueva.titulo,
          descripcion: this.nueva.descripcion,
          tags: Array.isArray(this.nueva.tagsSeleccionados)
            ? this.nueva.tagsSeleccionados.map(t=> String(t).trim().toLowerCase()).filter(Boolean)
            : [],
          user_id: this.currentUser.id
        })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo crear la pregunta');
        }
        return data;
      })
      .then(()=>{
        this.cargarPreguntas(1);
        if(this.vista === 'historial'){
          this.cargarHistorialPreguntas(1);
        }
        this.nueva={ titulo:'', descripcion:'', tagsSeleccionados: [] };
        this.tagBorrador = '';
        this.vista='inicio';
      })
      .catch(err=>{
        this.mostrarAviso(err.message);
      });
    },

    toggleResponder(questionId){
      if(!this.esProfesor){
        return this.mostrarAviso('Solo profesores pueden responder');
      }

      if(this.respondiendoPreguntaId === questionId){
        this.respondiendoPreguntaId = null;
        this.borradorRespuesta = '';
      }else{
        this.respondiendoPreguntaId = questionId;
        this.borradorRespuesta = '';
      }
    },

    enviarRespuesta(questionId){
      if(!this.esProfesor){
        return this.mostrarAviso('Solo profesores pueden responder');
      }

      if(!this.borradorRespuesta.trim()){
        return this.mostrarAviso('Escribe una respuesta');
      }

      fetch(`${API}/api/professors/${this.currentUser.id}/answers`,{
        method:'POST',
        headers:{
          'Content-Type':'application/json'
        },
        body: JSON.stringify({
          question_id: questionId,
          contenido: this.borradorRespuesta.trim()
        })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo publicar la respuesta');
        }
        return data;
      })
      .then(()=>{
        this.respondiendoPreguntaId = null;
        this.borradorRespuesta = '';
        this.cargarPreguntas();
      })
      .catch(err=>{
        this.mostrarAviso(err.message);
      });
    },

    comentarPregunta(questionId){
      if(!this.currentUser){
        return this.mostrarAviso('Debes iniciar sesion');
      }
      const contenido = (this.comentarioDraft[questionId] || '').trim();
      if(!contenido){
        return this.mostrarAviso('Escribe un comentario');
      }
      fetch(`${API}/api/questions/${questionId}/comments`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          user_id: this.currentUser.id,
          contenido
        })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo comentar');
      })
      .then(()=>{
        this.comentarioDraft[questionId] = '';
        this.cargarComentariosDePreguntas();
      })
      .catch(err=>this.mostrarAviso(err.message));
    },

    votarPregunta(questionId, tipo){
      if(!this.currentUser){
        return this.mostrarAviso('Debes iniciar sesion');
      }
      fetch(`${API}/api/questions/${questionId}/votes`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ user_id: this.currentUser.id, tipo })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo votar');
      })
      .then(()=>this.cargarVotosPreguntas())
      .catch(err=>this.mostrarAviso(err.message));
    },

    votarRespuesta(answerId, tipo){
      if(!this.currentUser){
        return this.mostrarAviso('Debes iniciar sesion');
      }
      fetch(`${API}/api/answers/${answerId}/votes`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ user_id: this.currentUser.id, tipo })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo votar');
      })
      .then(()=>this.cargarVotosRespuesta(answerId))
      .catch(err=>this.mostrarAviso(err.message));
    },

    renderMarkdown(text){
      if(!text) return '';
      if(window.marked && window.DOMPurify){
        const html = window.marked.parse(text);
        return window.DOMPurify.sanitize(html);
      }
      return text;
    },

    etiquetaIdiomaTraduccion(code){
      const map = { es: 'Español', en: 'Inglés', fr: 'Francés', pt: 'Portugués', de: 'Alemán', it: 'Italiano' };
      return map[code] || code;
    },

    reiniciarTraducciones(){
      this.traduccionesPreguntas = {};
      this.traduccionesRespuestas = {};
      this.traduccionesComentarios = {};
      this.traduccionesUI = {};
      this.traduccionGlobalActiva = false;
      this.traduccionGlobalCargando = false;
    },

    textoUI(clave){
      const original = TEXTOS_UI[clave];
      if(!original){
        return clave;
      }
      if(!this.traduccionGlobalActiva){
        return original;
      }
      return this.traduccionesUI[clave] ?? original;
    },

    uiTraduccionCompleta(){
      return Object.keys(TEXTOS_UI).every(
        (k) => this.traduccionesUI[k] && this.traduccionesUI._idioma === this.idiomaTraduccion,
      );
    },

    tituloPreguntaMostrado(p){
      if(!this.traduccionGlobalActiva){
        return p.titulo;
      }
      const t = this.traduccionesPreguntas[p.id];
      return t?.titulo ?? p.titulo;
    },

    contenidoPreguntaMostrado(p){
      if(!this.traduccionGlobalActiva){
        return p.contenido;
      }
      const t = this.traduccionesPreguntas[p.id];
      return t?.contenido ?? p.contenido;
    },

    contenidoRespuestaMostrado(r){
      if(!this.traduccionGlobalActiva){
        return r.contenido;
      }
      const t = this.traduccionesRespuestas[r.id];
      return t?.contenido ?? r.contenido;
    },

    contenidoComentarioMostrado(c){
      if(!this.traduccionGlobalActiva){
        return c.contenido;
      }
      const t = this.traduccionesComentarios[c.id];
      return t?.contenido ?? c.contenido;
    },

    paginaTraduccionCompleta(){
      if(!this.uiTraduccionCompleta()){
        return false;
      }
      if(!this.preguntas.length){
        return true;
      }
      for(const p of this.preguntas){
        const t = this.traduccionesPreguntas[p.id];
        if(!t || t.idioma !== this.idiomaTraduccion || t.titulo === undefined || t.contenido === undefined){
          return false;
        }
        for(const r of (this.respuestasPorPregunta[p.id] || [])){
          const tr = this.traduccionesRespuestas[r.id];
          if(!tr || tr.idioma !== this.idiomaTraduccion || tr.contenido === undefined){
            return false;
          }
        }
        for(const c of (this.comentariosPorPregunta[p.id] || [])){
          const tc = this.traduccionesComentarios[c.id];
          if(!tc || tc.idioma !== this.idiomaTraduccion || tc.contenido === undefined){
            return false;
          }
        }
      }
      return true;
    },

    idiomaDestinoEsEspanol(target){
      return (target || this.idiomaTraduccion || '').toLowerCase().split('-')[0] === 'es';
    },

    async llamarTraduccion(texts, target){
      const destino = (target || this.idiomaTraduccion || 'en').toLowerCase().split('-')[0];
      if(destino === 'es'){
        return { translations: [...texts], skipped: true };
      }
      const res = await fetch(`${API}/api/translate`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          texts,
          target: destino,
          source: 'es',
        }),
      });
      const data = await res.json().catch(()=>({}));
      if(!res.ok){
        const detalle = data.detail ? ` (${String(data.detail).slice(0, 120)})` : '';
        throw new Error((data.error || 'No se pudo traducir') + detalle);
      }
      if(!Array.isArray(data.translations) || !data.translations.length){
        throw new Error('Traduccion vacia');
      }
      return data;
    },

    async alternarTraduccionTodasPublicaciones(){
      if(this.traduccionGlobalCargando){
        return;
      }
      if(this.traduccionGlobalActiva){
        this.traduccionGlobalActiva = false;
        return;
      }
      if(this.paginaTraduccionCompleta()){
        this.traduccionGlobalActiva = true;
        return;
      }
      if(this.idiomaDestinoEsEspanol()){
        this.mostrarAviso('El foro ya está en español. Elige otro idioma (por ejemplo Inglés).');
        return;
      }
      this.traduccionGlobalCargando = true;
      try{
        await this.traducirPublicacionesPagina();
        this.traduccionGlobalActiva = true;
      }catch(err){
        this.mostrarAviso(err.message);
      }finally{
        this.traduccionGlobalCargando = false;
      }
    },

    async traducirLotesParalelos(texts, chunkSize = 20, maxConcurrent = 2){
      if(!texts.length){
        return [];
      }
      const lotes = [];
      for(let i = 0; i < texts.length; i += chunkSize){
        lotes.push(texts.slice(i, i + chunkSize));
      }
      const resultados = [];
      for(let i = 0; i < lotes.length; i += maxConcurrent){
        const oleada = lotes.slice(i, i + maxConcurrent);
        const oleadaDatos = await Promise.all(oleada.map((lote) => this.llamarTraduccion(lote)));
        resultados.push(...oleadaDatos);
      }
      return resultados.flatMap((data) => data.translations);
    },

    async traducirTextosUI(){
      const keys = Object.keys(TEXTOS_UI);
      const texts = keys.map((k) => TEXTOS_UI[k]);
      const traducciones = await this.traducirLotesParalelos(texts);
      keys.forEach((key, idx)=>{
        this.traduccionesUI[key] = traducciones[idx];
      });
      this.traduccionesUI._idioma = this.idiomaTraduccion;
    },

    aplicarTraduccionesJobs(jobs, traducciones){
      jobs.forEach((job, idx)=>{
        const translated = traducciones[idx];
        if(job.kind === 'pregunta'){
          const prev = this.traduccionesPreguntas[job.id] || {};
          this.traduccionesPreguntas[job.id] = {
            ...prev,
            [job.field]: translated,
            idioma: this.idiomaTraduccion,
          };
        }else if(job.kind === 'respuesta'){
          this.traduccionesRespuestas[job.id] = {
            contenido: translated,
            idioma: this.idiomaTraduccion,
          };
        }else{
          this.traduccionesComentarios[job.id] = {
            contenido: translated,
            idioma: this.idiomaTraduccion,
          };
        }
      });
    },

    recolectarJobsTraduccionContenido(){
      const jobs = [];
      for(const p of this.preguntas){
        jobs.push({ kind: 'pregunta', id: p.id, field: 'titulo', text: p.titulo || '' });
        jobs.push({ kind: 'pregunta', id: p.id, field: 'contenido', text: p.contenido || '' });
        for(const r of (this.respuestasPorPregunta[p.id] || [])){
          jobs.push({ kind: 'respuesta', id: r.id, field: 'contenido', text: r.contenido || '' });
        }
        for(const c of (this.comentariosPorPregunta[p.id] || [])){
          jobs.push({ kind: 'comentario', id: c.id, field: 'contenido', text: c.contenido || '' });
        }
      }
      return jobs;
    },

    async traducirContenidoPagina(){
      const jobs = this.recolectarJobsTraduccionContenido();
      if(!jobs.length){
        return;
      }
      const traducciones = await this.traducirLotesParalelos(jobs.map((j) => j.text));
      this.aplicarTraduccionesJobs(jobs, traducciones);
    },

    async traducirPublicacionesPagina(){
      await Promise.all([
        this.traducirTextosUI(),
        this.traducirContenidoPagina(),
      ]);
    },

    async editarPreguntaComoAdmin(question){
      if(!this.esModerador){
        return this.mostrarAviso('Solo administradores pueden moderar preguntas');
      }

      const nuevoTitulo = await this.promptTextoAsync('Nuevo titulo', question.titulo, 'Editar pregunta');
      if(nuevoTitulo === null){
        return;
      }
      const nuevoContenido = await this.promptTextoAsync('Nuevo contenido', question.contenido, 'Editar pregunta');
      if(nuevoContenido === null){
        return;
      }

      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/questions/${question.id}`, {
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({
          titulo: nuevoTitulo.trim(),
          contenido: nuevoContenido.trim()
        })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo moderar la pregunta');
        }
        return data;
      })
      .then(()=>{
        this.cargarPreguntas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async eliminarPreguntaComoAdmin(questionId){
      if(!this.esModerador){
        return this.mostrarAviso('Solo administradores pueden eliminar preguntas');
      }
      if(!(await this.confirmarAsync('¿Deseas eliminar esta pregunta? Esta acción no se puede deshacer.', 'Eliminar pregunta', 'Eliminar', 'Cancelar', { danger: true }))){
        return;
      }

      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/questions/${questionId}`, {
        method:'DELETE'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo eliminar la pregunta');
        }
        return data;
      })
      .then(()=>{
        this.cargarPreguntas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async editarRespuestaComoAdmin(answer){
      if(!this.esModerador){
        return this.mostrarAviso('Solo administradores pueden moderar respuestas');
      }

      const nuevoContenido = await this.promptTextoAsync('Nuevo contenido de la respuesta', answer.contenido, 'Editar respuesta');
      if(nuevoContenido === null){
        return;
      }

      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/answers/${answer.id}`, {
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ contenido: nuevoContenido.trim() })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo moderar la respuesta');
        }
        return data;
      })
      .then(()=>{
        this.cargarPreguntas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async eliminarRespuestaComoAdmin(answerId){
      if(!this.esModerador){
        return this.mostrarAviso('Solo administradores pueden eliminar respuestas');
      }
      if(!(await this.confirmarAsync('¿Deseas eliminar esta respuesta?', 'Eliminar respuesta', 'Eliminar', 'Cancelar', { danger: true }))){
        return;
      }

      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/answers/${answerId}`, {
        method:'DELETE'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo eliminar la respuesta');
        }
        return data;
      })
      .then(()=>{
        this.cargarPreguntas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    logout(){
      this.pantalla='inicio';
      this.currentUser=null;
      this.email='';
      this.password='';
      this.busqueda='';
      this.mensaje='';
      this.respuestasPorPregunta={};
      this.respondiendoPreguntaId=null;
      this.borradorRespuesta='';
    },

    enviarContacto(){
      if(!this.contacto.nombre || !this.contacto.mensaje){
        return this.mostrarAviso('Completa datos');
      }

      this.mostrarAviso('Gracias. Hemos recibido tu mensaje (demo local).', 'Contacto');
      this.contacto={nombre:'',mensaje:''};
    },

    rellenarPerfilForm(){
      if(!this.currentUser){
        return;
      }
      this.limpiarSeleccionAvatarPerfil();
      this.perfilForm={
        nombre:this.currentUser.nombre || '',
        email:this.currentUser.email || '',
        password:''
      };
    },

    limpiarSeleccionAvatarPerfil(){
      if(this.perfilAvatarPreview){
        URL.revokeObjectURL(this.perfilAvatarPreview);
      }
      this.perfilAvatarPreview = null;
      this.perfilAvatarFile = null;
      const el = this.$refs.perfilAvatarInput;
      if(el){
        el.value = '';
      }
    },

    onPerfilAvatarSeleccionado(e){
      const f = e.target.files && e.target.files[0];
      if(this.perfilAvatarPreview){
        URL.revokeObjectURL(this.perfilAvatarPreview);
        this.perfilAvatarPreview = null;
      }
      this.perfilAvatarFile = f || null;
      if(f){
        this.perfilAvatarPreview = URL.createObjectURL(f);
      }
    },

    subirFotoPerfil(){
      if(!this.currentUser){
        return this.mostrarAviso('Debes iniciar sesión');
      }
      if(!this.perfilAvatarFile){
        return this.mostrarAviso('Elige una imagen (JPEG, PNG o WebP, máximo 2 MB)');
      }
      const fd = new FormData();
      fd.append('avatar', this.perfilAvatarFile);
      fetch(`${API}/api/me/avatar`,{
        method:'POST',
        credentials:'include',
        body: fd
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo subir la imagen');
        }
        return data;
      })
      .then(data=>{
        this.currentUser = data.user;
        this.limpiarSeleccionAvatarPerfil();
        this.avatarCacheBust = Date.now();
        this.mostrarAviso('Foto de perfil actualizada');
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async quitarFotoPerfil(){
      if(!this.currentUser){
        return;
      }
      if(!(await this.confirmarAsync('¿Quitar tu foto y volver al avatar de Gravatar según tu correo?', 'Quitar foto de perfil', 'Quitar', 'Cancelar', { danger: true }))){
        return;
      }
      fetch(`${API}/api/me/avatar`,{
        method:'DELETE',
        credentials:'include'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo quitar la foto');
        }
        return data;
      })
      .then(data=>{
        this.currentUser = data.user;
        this.limpiarSeleccionAvatarPerfil();
        this.avatarCacheBust = Date.now();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    usuarioEstaActivo(u){
      if(!u || u.activo === undefined || u.activo === null){
        return true;
      }
      return Number(u.activo) === 1;
    },

    cargarUsuariosGlobales(){
      if(!this.esSuperAdmin){
        return;
      }
      fetch(`${API}/api/users`, { credentials:'include' })
        .then(async res=>{
          const data = await res.json();
          if(!res.ok){
            throw new Error(data.error || 'No se pudo cargar la lista');
          }
          return data;
        })
        .then(rows=>{
          this.usuariosGlobales = rows;
        })
        .catch(err=> this.mostrarAviso(err.message));
    },

    abrirEdicionUsuario(u){
      this.superEsCreacion = false;
      this.superEdit = {
        id: u.id,
        nombre: u.nombre || '',
        email: u.email || '',
        password: '',
        rol: u.rol || 'estudiante'
      };
      this.superUsuarioFormActivo = true;
    },

    abrirCreacionUsuario(){
      this.superEsCreacion = true;
      this.superEdit = { id: null, nombre: '', email: '', password: '', rol: 'estudiante' };
      this.superUsuarioFormActivo = true;
    },

    cerrarFormSuperUsuario(){
      this.superUsuarioFormActivo = false;
      this.superEsCreacion = false;
      this.superEdit = { id: null, nombre: '', email: '', password: '', rol: 'estudiante' };
    },

    guardarUsuarioSuper(){
      if(!this.esSuperAdmin || !this.superUsuarioFormActivo){
        return;
      }
      if(this.superEsCreacion){
        const nombre = this.superEdit.nombre.trim();
        const email = this.superEdit.email.trim();
        const pwd = this.superEdit.password;
        if(!nombre || !email){
          return this.mostrarAviso('Nombre y correo son obligatorios');
        }
        if(!pwd || String(pwd).length < 6){
          return this.mostrarAviso('Contraseña obligatoria (mín. 6 caracteres)');
        }
        return fetch(`${API}/api/superadmin/users`,{
          method:'POST',
          credentials:'include',
          headers:{ 'Content-Type':'application/json' },
          body: JSON.stringify({
            nombre,
            email,
            password: pwd,
            rol: this.superEdit.rol
          })
        })
        .then(async res=>{
          const data = await res.json();
          if(!res.ok){
            throw new Error(data.error || 'No se pudo crear el usuario');
          }
          return data;
        })
        .then(()=>{
          this.mostrarAviso('Usuario creado');
          this.cerrarFormSuperUsuario();
          this.cargarUsuariosGlobales();
        })
        .catch(err=> this.mostrarAviso(err.message));
      }
      if(!this.superEdit.id){
        return;
      }
      const body = {
        nombre: this.superEdit.nombre.trim(),
        email: this.superEdit.email.trim(),
        rol: this.superEdit.rol
      };
      if(this.superEdit.password){
        body.password = this.superEdit.password;
      }
      fetch(`${API}/api/superadmin/users/${this.superEdit.id}`,{
        method:'PATCH',
        credentials:'include',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo guardar');
        }
        return data;
      })
      .then(()=>{
        const editedId = this.superEdit.id;
        this.mostrarAviso('Usuario actualizado');
        this.cerrarFormSuperUsuario();
        this.cargarUsuariosGlobales();
        if(this.currentUser && this.currentUser.id === editedId){
          this.currentUser.nombre = body.nombre;
          this.currentUser.email = body.email;
          this.currentUser.rol = body.rol;
        }
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async desactivarUsuarioSuper(uid){
      if(!this.esSuperAdmin){
        return;
      }
      if(uid === this.currentUser.id){
        return this.mostrarAviso('No puedes desactivar tu propia sesion desde aqui');
      }
      if(!(await this.confirmarAsync('El usuario quedara inactivo y no podra iniciar sesion. ¿Continuar?', 'Desactivar usuario', 'Desactivar', 'Cancelar', { danger: true }))){
        return;
      }
      fetch(`${API}/api/superadmin/users/${uid}`,{
        method:'DELETE',
        credentials:'include'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo desactivar');
        }
        return data;
      })
      .then(()=>{
        this.mostrarAviso('Usuario desactivado');
        this.cargarUsuariosGlobales();
        if(this.superUsuarioFormActivo && this.superEdit.id === uid){
          this.cerrarFormSuperUsuario();
        }
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    reactivarUsuarioSuper(uid){
      if(!this.esSuperAdmin){
        return;
      }
      fetch(`${API}/api/superadmin/users/${uid}`,{
        method:'PATCH',
        credentials:'include',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ activo: true })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok){
          throw new Error(data.error || 'No se pudo reactivar');
        }
        return data;
      })
      .then(()=>{
        this.mostrarAviso('Usuario reactivado');
        this.cargarUsuariosGlobales();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    guardarPerfil(){
      if(!this.currentUser){
        return this.mostrarAviso('Debes iniciar sesión');
      }
      const nombre = (this.perfilForm.nombre || '').trim();
      const email = (this.perfilForm.email || '').trim();
      if(!nombre || !email){
        return this.mostrarAviso('Nombre y correo son obligatorios');
      }
      const body = { nombre, email };
      if(this.perfilForm.password){
        body.password = this.perfilForm.password;
      }

      const habiaFotoPendiente = !!this.perfilAvatarFile;

      const patchProfile = () =>
        fetch(`${API}/api/me`,{
          method:'PATCH',
          credentials:'include',
          headers:{ 'Content-Type':'application/json' },
          body: JSON.stringify(body)
        })
        .then(async res=>{
          const data = await res.json();
          if(!res.ok){
            throw new Error(data.error || 'No se pudo actualizar el perfil');
          }
          return data;
        });

      const uploadAvatarIfSelected = () => {
        if(!this.perfilAvatarFile){
          return Promise.resolve(null);
        }
        const fd = new FormData();
        fd.append('avatar', this.perfilAvatarFile);
        return fetch(`${API}/api/me/avatar`,{
          method:'POST',
          credentials:'include',
          body: fd
        })
        .then(async res=>{
          const data = await res.json();
          if(!res.ok){
            throw new Error(data.error || 'No se pudo subir la imagen');
          }
          return data;
        })
        .then(data=>{
          this.currentUser = data.user;
          this.limpiarSeleccionAvatarPerfil();
          this.avatarCacheBust = Date.now();
        });
      };

      uploadAvatarIfSelected()
        .then(()=> patchProfile())
        .then(data=>{
          this.currentUser = data.user;
          this.perfilForm.password = '';
          this.mensaje = `Bienvenido, ${data.user.nombre} (${data.user.rol})`;
          this.avatarCacheBust = Date.now();
          this.mostrarAviso(habiaFotoPendiente ? 'Perfil y foto actualizados' : 'Perfil actualizado');
        })
        .catch(err=> this.mostrarAviso(err.message));
    },

    irAula(){
      this.vista = 'aula';
      this.aulaEntregasDe = null;
      this.aulaEntregasEsModeracion = false;
      this.aulaEntregasLista = [];
      this.aulaGradesDraft = {};
      this.aulaComentariosPorTarea = {};
      this.aulaReplyParentId = null;
      this.aulaReplyAssignmentId = null;
      this.cargarAulaTareas();
    },

    formatDatetimeLocal(val){
      if(!val) return '';
      const s = String(val).replace(' ', 'T');
      if(s.length >= 16) return s.slice(0, 16);
      return s;
    },

    /** Fecha legible para listados (aula, comentarios). */
    formatFechaHumana(val){
      if(val == null || val === '') return '';
      try{
        const d = val instanceof Date ? val : new Date(val);
        if(Number.isNaN(d.getTime())) return String(val);
        return d.toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' });
      } catch{
        return String(val);
      }
    },

    /** Comparacion robusta (API puede devolver id como numero o string). */
    aulaEsDueñoDeTarea(t){
      if(!this.currentUser || !t){
        return false;
      }
      return Number(t.professor_id) === Number(this.currentUser.id);
    },

    /** Puede actuar como docente de esta tarea (dueño o superadmin). */
    aulaDocenteDeTarea(t){
      if(!this.currentUser || !t){
        return false;
      }
      if(this.esSuperAdmin){
        return true; 
      }
      return this.aulaEsDueñoDeTarea(t);
    },

    borradorEstudianteAula(tareaId){
      if(!this.aulaEstudianteBorrador[tareaId]){
        this.aulaEstudianteBorrador[tareaId] = { texto: '', privado: false };
      }
      return this.aulaEstudianteBorrador[tareaId];
    },

    refrescarComentariosTarea(assignmentId){
      const uid = this.currentUser && this.currentUser.id;
      if(!uid){
        this.aulaComentariosPorTarea[assignmentId] = [];
        return Promise.resolve();
      }
      return fetch(`${API}/api/assignments/${assignmentId}/comments?viewer_user_id=${uid}`)
        .then(r=>r.json())
        .then(rows=>{
          this.aulaComentariosPorTarea[assignmentId] = Array.isArray(rows) ? rows : [];
        })
        .catch(()=>{ this.aulaComentariosPorTarea[assignmentId] = []; });
    },

    aulaDownloadUrl(submissionId){
      if(!this.currentUser) return '#';
      const path = `/api/assignment-submissions/${submissionId}/download?user_id=${this.currentUser.id}`;
      return API ? `${API}${path}` : path;
    },

    cargarAulaTareas(){
      let url = `${API}/api/assignments`;
      if(this.esEstudianteEnAula && this.currentUser){
        url += '?for_student_id=' + encodeURIComponent(String(this.currentUser.id));
      }
      fetch(url)
        .then(r=>r.json())
        .then(data=>{
          this.aulaTareas = Array.isArray(data) ? data : [];
          const ids = this.aulaTareas.map(t=>t.id);
          return Promise.all(ids.map(id=>this.refrescarComentariosTarea(id)));
        })
        .catch(()=>{ this.aulaTareas = []; });
    },

    publicarTareaAula(){
      if(!this.esProfesorEnAula || !this.currentUser){
        return this.mostrarAviso('Solo profesores o el administrador supremo pueden publicar tareas');
      }
      const titulo = (this.aulaNueva.titulo || '').trim();
      if(!titulo){
        return this.mostrarAviso('Escribe un titulo');
      }
      const body = {
        titulo,
        descripcion: (this.aulaNueva.descripcion || '').trim()
      };
      const fe = (this.aulaNueva.fecha_entrega || '').trim();
      if(fe){
        body.fecha_entrega = fe;
      }
      fetch(`${API}/api/professors/${this.currentUser.id}/assignments`,{
        method:'POST',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo publicar');
        return data;
      })
      .then(()=>{
        this.aulaNueva = { titulo: '', descripcion: '', fecha_entrega: '' };
        this.cargarAulaTareas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async eliminarTareaAula(t){
      if(!this.esProfesorEnAula || !this.currentUser){
        return;
      }
      if(!this.aulaDocenteDeTarea(t)){
        return;
      }
      if(!(await this.confirmarAsync('Se eliminarán todas las entregas y comentarios de esta tarea.', 'Eliminar tarea', 'Eliminar', 'Cancelar', { danger: true }))){
        return;
      }
      fetch(`${API}/api/professors/${this.currentUser.id}/assignments/${t.id}`,{
        method:'DELETE'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo eliminar');
      })
      .then(()=>{
        if(this.aulaEntregasDe === t.id){
          this.cerrarEntregasAula();
        }
        this.cargarAulaTareas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    verEntregasAula(t){
      if(!this.esProfesorEnAula || !this.currentUser){
        return;
      }
      if(!this.aulaDocenteDeTarea(t)){
        return;
      }
      this.aulaEntregasEsModeracion = false;
      this.aulaEntregasDe = t.id;
      fetch(`${API}/api/assignments/${t.id}/submissions?professor_id=${this.currentUser.id}`)
        .then(r=>r.json())
        .then(data=>{
          this.aulaEntregasLista = Array.isArray(data) ? data : [];
          const draft = {};
          this.aulaEntregasLista.forEach(e=>{
            draft[e.id] = {
              nota: e.nota != null && e.nota !== '' ? String(e.nota) : '',
              comentario: e.comentario_profesor || ''
            };
          });
          this.aulaGradesDraft = draft;
        })
        .catch(()=>{ this.aulaEntregasLista = []; this.aulaGradesDraft = {}; });
    },

    cerrarEntregasAula(){
      this.aulaEntregasDe = null;
      this.aulaEntregasEsModeracion = false;
      this.aulaEntregasLista = [];
      this.aulaGradesDraft = {};
    },

    verEntregasAulaAdmin(t){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      this.aulaEntregasEsModeracion = true;
      this.aulaEntregasDe = t.id;
      this.aulaGradesDraft = {};
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignments/${t.id}/submissions`)
        .then(r=>r.json())
        .then(data=>{
          this.aulaEntregasLista = Array.isArray(data) ? data : [];
        })
        .catch(()=>{ this.aulaEntregasLista = []; });
    },

    moderarFechaEntregaAulaAdmin(t, ev){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      const v = (ev.target.value || '').trim();
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignments/${t.id}`,{
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ fecha_entrega: v || null })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>this.cargarAulaTareas())
      .catch(err=> this.mostrarAviso(err.message));
    },

    quitarFechaEntregaAulaAdmin(t){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignments/${t.id}`,{
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ fecha_entrega: null })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>this.cargarAulaTareas())
      .catch(err=> this.mostrarAviso(err.message));
    },

    async moderarTituloDescAulaAdmin(t){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      const titulo = await this.promptTextoAsync('Titulo de la tarea', t.titulo || '', 'Editar tarea (moderación)');
      if(titulo === null){
        return;
      }
      const tit = titulo.trim();
      if(!tit){
        return this.mostrarAviso('El titulo no puede quedar vacio');
      }
      const descripcion = await this.promptTextoAsync('Descripcion / instrucciones (puede quedar vacio)', t.descripcion || '', 'Editar tarea (moderación)');
      if(descripcion === null){
        return;
      }
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignments/${t.id}`,{
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({
          titulo: tit,
          descripcion: (descripcion || '').trim() || null
        })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>this.cargarAulaTareas())
      .catch(err=> this.mostrarAviso(err.message));
    },

    async eliminarTareaAulaAdmin(t){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      if(!(await this.confirmarAsync('Se eliminarán entregas, archivos y comentarios.', 'Eliminar tarea (moderación)', 'Eliminar', 'Cancelar', { danger: true }))){
        return;
      }
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignments/${t.id}`,{
        method:'DELETE'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo eliminar');
      })
      .then(()=>{
        if(this.aulaEntregasDe === t.id){
          this.cerrarEntregasAula();
        }
        this.cargarAulaTareas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    async editarComentarioAulaAdmin(t, c){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      const contenido = await this.promptTextoAsync('Contenido del comentario', c.contenido || '', 'Editar comentario');
      if(contenido === null){
        return;
      }
      const txt = contenido.trim();
      if(!txt){
        return this.mostrarAviso('El contenido no puede quedar vacio');
      }
      const privRaw = await this.promptTextoAsync(
        'Visibilidad: escribe 1 (privado), 0 (publico), o deja vacio para no cambiar',
        '',
        'Visibilidad del comentario'
      );
      if(privRaw === null){
        return;
      }
      const body = { contenido: txt };
      const pr = String(privRaw).trim();
      if(pr === '0' || pr === '1'){
        body.is_private = pr === '1';
      }
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignment-comments/${c.id}`,{
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>this.refrescarComentariosTarea(t.id))
      .catch(err=> this.mostrarAviso(err.message));
    },

    async eliminarComentarioAulaAdmin(t, c){
      if(!this.esModerador || !this.currentUser){
        return;
      }
      if(!(await this.confirmarAsync('Se eliminarán también las respuestas enlazadas si las hay.', 'Eliminar comentario', 'Eliminar', 'Cancelar', { danger: true }))){
        return;
      }
      fetch(`${API}/api/admins/${this.currentUser.id}/moderation/assignment-comments/${c.id}`,{
        method:'DELETE'
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo eliminar');
      })
      .then(()=>this.refrescarComentariosTarea(t.id))
      .catch(err=> this.mostrarAviso(err.message));
    },

    actualizarFechaEntregaAula(t, ev){
      if(!this.esProfesorEnAula || !this.currentUser){
        return;
      }
      if(!this.aulaDocenteDeTarea(t)){
        return;
      }
      const v = (ev.target.value || '').trim();
      fetch(`${API}/api/professors/${this.currentUser.id}/assignments/${t.id}`,{
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ fecha_entrega: v || null })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>this.cargarAulaTareas())
      .catch(err=> this.mostrarAviso(err.message));
    },

    quitarFechaEntregaAula(t){
      if(!this.esProfesorEnAula || !this.currentUser){
        return;
      }
      if(!this.aulaDocenteDeTarea(t)){
        return;
      }
      fetch(`${API}/api/professors/${this.currentUser.id}/assignments/${t.id}`,{
        method:'PUT',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({ fecha_entrega: null })
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>this.cargarAulaTareas())
      .catch(err=> this.mostrarAviso(err.message));
    },

    publicarComentarioAula(t){
      if(!this.esProfesorEnAula || !this.currentUser){
        return;
      }
      if(!this.aulaDocenteDeTarea(t)){
        return;
      }
      const contenido = (this.aulaComentarioDraft[t.id] || '').trim();
      if(!contenido){
        return this.mostrarAviso('Escribe un comentario');
      }
      const body = {
        professor_id: this.currentUser.id,
        contenido
      };
      if(this.aulaReplyParentId && this.aulaReplyAssignmentId === t.id){
        body.parent_id = this.aulaReplyParentId;
      }
      fetch(`${API}/api/assignments/${t.id}/comments`,{
        method:'POST',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo publicar');
      })
      .then(()=>{
        this.aulaComentarioDraft[t.id] = '';
        this.aulaReplyParentId = null;
        this.aulaReplyAssignmentId = null;
        this.refrescarComentariosTarea(t.id);
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    iniciarRespuestaAula(assignmentId, comentario){
      this.aulaReplyAssignmentId = assignmentId;
      this.aulaReplyParentId = comentario.id;
    },

    cancelarRespuestaAula(){
      this.aulaReplyParentId = null;
      this.aulaReplyAssignmentId = null;
    },

    publicarComentarioEstudianteAula(t){
      if(!this.esEstudianteEnAula || !this.currentUser){
        return this.mostrarAviso('Solo estudiantes o el administrador supremo pueden publicar aqui');
      }
      const b = this.borradorEstudianteAula(t.id);
      if(!b){
        return;
      }
      const contenido = (b.texto || '').trim();
      if(!contenido){
        return this.mostrarAviso('Escribe un mensaje');
      }
      const body = {
        contenido,
        is_private: !!b.privado
      };
      if(this.aulaReplyParentId && this.aulaReplyAssignmentId === t.id){
        body.parent_id = this.aulaReplyParentId;
      }
      fetch(`${API}/api/students/${this.currentUser.id}/assignments/${t.id}/comments`,{
        method:'POST',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo publicar');
      })
      .then(()=>{
        b.texto = '';
        b.privado = false;
        this.aulaReplyParentId = null;
        this.aulaReplyAssignmentId = null;
        this.refrescarComentariosTarea(t.id);
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    guardarCalificacionAula(e){
      if(!this.esProfesorEnAula || !this.currentUser){
        return;
      }
      const d = this.aulaGradesDraft[e.id];
      if(!d){
        return;
      }
      let notaPayload = null;
      if(d.nota !== undefined && String(d.nota).trim() !== ''){
        const n = parseFloat(String(d.nota).replace(',', '.'));
        if(Number.isNaN(n)){
          return this.mostrarAviso('La nota debe ser un numero (0 a 10)');
        }
        notaPayload = n;
      }
      const body = {
        nota: notaPayload,
        comentario_profesor: (d.comentario || '').trim() || null
      };
      fetch(`${API}/api/professors/${this.currentUser.id}/submissions/${e.id}/grade`,{
        method:'PATCH',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo guardar');
      })
      .then(()=>{
        this.mostrarAviso('Calificación guardada.', 'Hecho');
        const t = this.aulaTareas.find(x=>x.id === this.aulaEntregasDe);
        if(t) this.verEntregasAula(t);
        this.cargarAulaTareas();
      })
      .catch(err=> this.mostrarAviso(err.message));
    },

    subirEntregaAula(assignmentId, ev){
      if(!this.esEstudianteEnAula || !this.currentUser){
        return this.mostrarAviso('Solo estudiantes o el administrador supremo entregan archivos');
      }
      const file = ev.target.files && ev.target.files[0];
      if(!file){
        return;
      }
      const fd = new FormData();
      fd.append('file', file);
      fetch(`${API}/api/students/${this.currentUser.id}/assignments/${assignmentId}/submit`,{
        method:'POST',
        body: fd
      })
      .then(async res=>{
        const data = await res.json();
        if(!res.ok) throw new Error(data.error || 'No se pudo subir');
        return data;
      })
      .then(()=>{
        ev.target.value = '';
        this.cargarAulaTareas();
        this.mostrarAviso('Entrega registrada correctamente.', 'Hecho');
      })
      .catch(err=> this.mostrarAviso(err.message));
    }

  }

}).mount('#app');
