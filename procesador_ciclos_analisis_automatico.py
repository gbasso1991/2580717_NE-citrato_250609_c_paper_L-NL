#%% 
'''
procesador_ciclos_autom_analis_automatico.py

Giuliano Andrés Basso

Optimizado para procesar ciclos salvados por 'OWON_con_python.py'

IMPORTANTE: requiere 'funciones_del_procesador.py' en el mismo directorio

La configuracion y el procesamiento siguen basicamente igual, pero restrinjo salidas graficas y tablas

Grafica todos los ciclos
Grafica todos los ciclos filtrados

17 Mayo 24
Detecta entre los primeros/ultimos 10 files aquellos cuya magnetizacion es inusualmente baja
correspondientes al ingreso/salida de la muestra en la bobina

10 Julio 24
Calcula el tiempo de transicion de fase utilizando criterio en T y en dT/dt 

18 Julio 24
Toma la hora guardada en archivos (1er fila a comentario, por lo que tmb se modifico OWON_con_python.py)
Interpola t y T del templog entre tiempo de las medidas (dt=0.01, dT=0.01) y asigna Temperatura a cada muestra en base a eso

11 Sept 24
Optimizado para calcular la pendiente del ciclo del paramagneto

04 Oct 24
Actualizada constante de calibracion del paramagneto, calculada para bobina captora de N=1 espira
'''
import time
start_time = time.time()
import os
import fnmatch
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cmx
import matplotlib as mpl
import pandas as pd
import tkinter as tk
import scipy as sc
import shutil
from scipy.signal import find_peaks
from scipy.integrate import cumulative_trapezoid, trapezoid
from scipy.fft import fft, ifft, rfftfreq,irfft
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
from astropy.io import ascii
from astropy.table import Table, Column, MaskedColumn
from sklearn.metrics import r2_score
from pprint import pprint
from tkinter import filedialog
from uncertainties import ufloat, unumpy
from datetime import datetime,timedelta
from numpy.core.numeric import indices
from funciones_procesado import medida_cruda, medida_cruda_autom,ajusta_seno, sinusoide,resta_inter,filtrando_ruido,recorte,promediado_ciclos,fourier_señales_5,lector_templog_2,lector_templog,susceptibilidad_M_0

#%% Configuracion de Script
todos=1
un_solo_fondo=1
resto_fondo=1
templog = 0
N_espiras_bob_captora=5
nombre='*NE'
Analisis_de_Fourier = 1 # sobre las señales, imprime espectro de señal muestra
N_armonicos_impares = 10
concentracion =9.7*1e3 #[concentracion]= g/m^3 (1 g/l == 1e3 g/m^3) (Default = 10000 g/m^3)
capsula_glucosa=0   # capsula para solventes organicos
detector_ciclos_descartables=True #en funcion a Mag max para evitar guardar/promediar con ciclos in/out
Ciclo_promedio=0
Transicion_de_fase=0
#¿Qué gráficos desea ver? (1 = sí, ~1 = no)
graficos={
        'Referencias_y_ajustes': 0,
        'Resta_m-f': 0,
        'Resta_c-f': 0,
        'Resta_mf_y_cf':0,
        'Filtrado_calibracion': 0,
        'Filtrado_muestra': 0,
        'Recorte_a_periodos_enteros_c': 0,
        'Recorte_a_periodos_enteros_m': 0,
        'Campo_y_Mag_norm_c': 0,
        'Ciclos_HM_calibracion': 0,
        'Campo_y_Mag_norm_m': 0,
        'Ciclo_HM_m': 0,
        'Susceptibilidad_M_0':0,
        'Ciclos_HM_m_todos': 1}
mu_0 = 4*np.pi*10**-7 #[mu_0]=N/A^2
# =============================================================================
#Calibracion del campo en la bobina: cte que dimensionaliza al campo en A/m a partir de la calibracion
#realizada sobre la bobina  del RF
# Valores actualizados en mar 2023 con medidas hechas por Giuliano en 2022 y las calibraciones de sonda Hall
pendiente_HvsI = 3716.3 # 1/m
ordenada_HvsI = 1297.0 # A/m
# =============================================================================
#Calibracion de la magnetizacion: cte que dimensionaliza a M en Vs --> A/m
xi_patron_Dy2O3_v = 5.351e-3 #adimensional. Valor de VSM sobre capsula

if N_espiras_bob_captora==5:
    pendiente_patron_Dy2O3 = ufloat(2.0861745031033012e-13,5.773563581411776e-14) #Vsm/A - (N=5 27 Nov 24)
elif N_espiras_bob_captora==1:
    pendiente_patron_Dy2O3 = ufloat(4.584443008514465e-14,4.441474310168033e-15) #Vsm/A - (N=1 30 Sept 24)
else:
    print('Especificar Num de espiras del par captor')
#aca podria agregar algo para checkear que N coincida con el de nombre de archivo
C_Vs_to_Am_magnetizacion = xi_patron_Dy2O3_v/pendiente_patron_Dy2O3.nominal_value #A/mVs
if capsula_glucosa ==1:
    C_Vs_to_Am_magnetizacion = C_Vs_to_Am_magnetizacion*0.506
# =============================================================================
# Imprimo configuraciones
print(time.strftime('%Y %m %d', time.localtime()),'-'*50)
print('Configuracion del script:')
print(f'''
      Dir de trabajo: {os.getcwd()}
      Selecciono todos los archivos del directorio: {bool(todos)}
      Resto señal de fondo: {bool(resto_fondo)}
      Identificador de archivos de muestra': {nombre}
      N° de espiras x bobina captora: {N_espiras_bob_captora}
      Filtrado en armonicos impares: {bool(Analisis_de_Fourier)}
      Num de armonicos impares considerados: {N_armonicos_impares}
      Templog: {bool(templog)}
      Concentracion: {concentracion/1000} g/l
      ''','\n','-'*60)

#%%Defino listas para almacenar datos en cada iteracion
long_arrays=[]
Ciclos_eje_H = []
Ciclos_eje_M = []
Ciclos_eje_M_filt =[]
Ciclos_tiempo=[]
Ciclos_eje_H_ua=[]
Ciclos_eje_M_ua=[]
    
Frecuencia_ref_muestra_kHz = []

Frecuencia_ref_fondo_kHz = []
Frec_fund=[]
SAR = []
SAR_filt=[]
SAR_area=[]
Campo_maximo = []
Mag_max=[]
Coercitividad_kAm = []
Remanencia_Am = []

Tau=[]
Frec_fem = []
Defasaje_1er_arm = []
Magnitud_1er_arm = []
xi_M_0=[]

cociente_f1_f0 = []
cociente_f2_f0 = []

#Fecha para usar en graficos
fecha_nombre = datetime.today().strftime('%Y%m%d_%H%M%S')
fecha_graf = time.strftime('%Y_%m_%d', time.localtime())


#%% Seleccion de carpeta con archivos via interfaz de usuario
root = tk.Tk()
root.withdraw()
if todos==1: #Leo todos los archivos del directorio
    texto_encabezado = "Seleccionar la carpeta con las medidas a analizar:"
    directorio = filedialog.askdirectory(title=texto_encabezado)
    filenames = [f for f in os.listdir(directorio) if f.endswith('.txt')] #todos
    filenames.sort()
    print('Directorio de trabajo: \n'+ directorio +'\n')
    print(f'{len(filenames)} archivos en el directorio:\n')

    fnames_f = [filenames[0]]
    path_f = [os.path.join(directorio,filenames[0])]
    fnames_m = filenames[1:] # 1ero es fondo y ultimo para testear descancelacion. Lo proceso y lo separo despues
    path_m = [os.path.join(directorio,f) for f in fnames_m] #todos los demas

    for idx_m, m in enumerate(fnames_m):
        print(idx_m,'-',m)
    print('.'*40)
    print('Archivos de fondo en el directorio:\n')
    for idx_f,f in enumerate(fnames_f):
        print(idx_f,'-',f)

    print(f'\nSon {len(fnames_m)}/{len(fnames_m)+len(fnames_f)} archvos de muestra, {len(fnames_f)}/{len(fnames_m)+len(fnames_f)} de fondo')

    print('-'*50)
else:
    print('''setear: 'todos=1' ''')

if len(fnames_m)==0:
    raise Exception(f'No se seleccionaron archivos de muestra.\nIdentificador: {nombre}')
#Creo carpeta para guardar analisis
output_dir = os.path.join(directorio,f'Analisis_{fecha_nombre}') # Directorio donde se guardarán los resultados
if not os.path.exists(output_dir): # Crear el directorio si no existe
    os.makedirs(output_dir)

#%% Parametros a partir de nombre del archivo
frec_nombre=[]      #Frec del nombre del archivo. Luego comparo con frec ajustada
Idc = []            #Internal direct current en el generador de RF
delta_t = []        #Base temporal
fecha_m = []        #fecha de creacion archivo, i.e., de la medida

for i in range(len(fnames_m)):
    frec_nombre.append(float(fnames_m[i].split('_')[0][:-3])*1000)
    Idc.append(float(fnames_m[i].split('_')[1][:-2])/10)
    delta_t.append(1e-6/float(fnames_m[i].split('_')[2][:-3])) #A partir del sampleo configurado en en el osciloscopio
    fecha_m.append(datetime.fromtimestamp(os.path.getmtime(path_m[i])).strftime('%Y-%m-%d- %H:%M')) #Usar tiempo de MODIFICACION


#%% TEMPLOG --> FECHA POSTA E INTERPOLACION DE LA TEMPERATURA (18 Jul 24)

# Levanto hora guardada en los archivos 
Fechas_from_file = []
Fechas_from_file_descancelacion=[]

for k in range(len(fnames_m)):
    with open(path_m[k], 'r') as f:
        fecha_in_file = f.readline()
        Fechas_from_file.append(fecha_in_file.split()[-1])
        
#%%
with open(path_m[-1], 'r') as f:
    fecha_in_file_f = f.readline().split()[-1]
    Fechas_from_file_descancelacion.append(fecha_in_file_f)

if templog:
    try:
        timestamp,temperatura,__ = lector_templog(directorio,plot=True)
        t_full = np.array([(t-timestamp[0]).total_seconds() for t in timestamp])
        T_full= temperatura
        dates_m = [datetime.strptime(f, '%y%m%d_%H:%M:%S.%f') for f in Fechas_from_file[:-1]] #datetimes c/ fecha de archivos 
        time_delta=[t.total_seconds() for t in np.diff(dates_m)] #dif de tiempo entre archivos c resolucion 0.01 s
        time_delta.insert(0,0)
        delta_0 = (dates_m[0] - timestamp[0]).total_seconds() # entre comienzo del templog y 1er archivo redondeado a .2f
        #busco el indice en el templog que corresponde al segundo del 1er y ultimo dato para extrapolar tiempo y Temperatura 
        indx_1er_dato=np.nonzero(timestamp==dates_m[0].replace(microsecond=0))[0][0]
        indx_ultimo_dato=np.nonzero(timestamp==datetime.strptime(Fechas_from_file_descancelacion[0], '%y%m%d_%H:%M:%S.%f').replace(microsecond=0))[0][0]
        #Interpolo t entre tiempo de 1er y ultimo ciclo 
        interp_func = interp1d(t_full, T_full, kind='linear')
        tiempo_interpolado = np.round(np.arange(t_full[indx_1er_dato], t_full[indx_ultimo_dato]+1.01,0.01),2)
        temperatura_interpolada= np.round(interp_func(tiempo_interpolado),2)

        time_m = np.round(delta_0 + np.cumsum(time_delta),2)
        temp_m = np.array([temperatura_interpolada[np.flatnonzero(tiempo_interpolado==t)[0]] for t in time_m])

        cmap = mpl.colormaps['jet'] #'viridis'
        normalized_temperaturas = (np.array(temp_m) - np.array(temp_m).min()) / (np.array(temp_m).max() - np.array(temp_m).min())
        colors = cmap(normalized_temperaturas)

        fig2,ax=plt.subplots(figsize=(10,5.5),constrained_layout=True)
        ax.plot(t_full,T_full,'.-',label='Templog (Rugged O201)')
        ax.plot(tiempo_interpolado,temperatura_interpolada,'-',label='Temperatura interpolada')
        ax.scatter(time_m,temp_m,color=colors,label='Temperatura muestra')

        plt.xlabel('t (s)')
        plt.ylabel('T (°C)')
        plt.legend(loc='lower right')
        plt.grid()
        plt.title('Temperatura de la muestra',fontsize=18)
        plt.savefig(os.path.join(output_dir,os.path.commonprefix(fnames_m)+'_templog.png'),dpi=300,facecolor='w')
        plt.show()

    except IndexError:
        print('El horario de los archivos no se encuentra en el templog\n')
        print(f'''Inicio del templog: {timestamp[0]}\n\nDatetime primer archivo: {dates_m[0]}\n\nDatetime ultimo archivo: {dates_m[-1]}\n\nFin del templog: {timestamp[-1]}\n''')

else:
    print('No se requiere archivo con templog')
    temp_m=np.array([float(20) for f in fnames_m])
    cmap = mpl.colormaps['jet']  #'viridis' # Crear un rango de colores basado en las temperaturas y el cmap
    norm = plt.Normalize(temp_m.min(), temp_m.max())


 #%% DETERMINACION DE LA TRANSICION DE FASE
if Transicion_de_fase==1:
    T_m = temp_m
    dT_dt = np.gradient(T_m,time_m)
    
    filtro_T = (-1,0.2)     #ºC 
    filtro_dT_dt=0.15 #ºC/s
    indx_TF=np.nonzero((T_m>filtro_T[0])&(T_m<filtro_T[1])&(abs(dT_dt)<filtro_dT_dt))

    indx_TF_interp= np.nonzero((tiempo_interpolado>=time_m[indx_TF[0][0]]) & ( tiempo_interpolado<= time_m[indx_TF[0][-1]]))
    t_tf= round(time_m[indx_TF[0][-1]] - time_m[indx_TF[0][0]],2)
    t_tf_interp= round(tiempo_interpolado[indx_TF_interp[0][-1]] - tiempo_interpolado[indx_TF_interp[0][0]],2)

    fig,(ax,ax2)= plt.subplots(nrows=2,figsize=(10,8),sharex=True,constrained_layout=True)
    ax.plot(time_m,T_m , '.-',label='Temperatura',zorder=2)
    ax.plot(time_m[indx_TF], T_m[indx_TF], 'go-',label='Transicion de Fase',zorder=1)
    # ax.axvspan(tiempo_interpolado[indx_TF_interp[0][0]],tiempo_interpolado[indx_TF_interp[0][-1]],color='tab:red',alpha=0.5,label=f'T Fase ({filtro_T[0]}<T<{filtro_T[1]} ºC)',zorder=0)
    # ax.plot(time_m[indx_TF],T_m[indx_TF] , 'g.-')

    ax2.plot(time_m,dT_dt , '.-',label='dT/dt')
    # ax2.axvspan(tiempo_interpolado[indx_TF_interp[0][0]],tiempo_interpolado[indx_TF_interp[0][-1]],color='tab:red',alpha=0.5,label=f'T Fase (|dT/dt| <{filtro_dT_dt} ºC/s)',zorder=-2)
    ax2.axhline(y=filtro_dT_dt, color='k',lw=1, linestyle='--')
    ax2.axhline(y=-filtro_dT_dt, color='k',lw=1, linestyle='--')
    ax2.set_xlabel('t (s)')
    ax.set_ylabel('T (ºC)')
    ax2.set_ylabel('dT/dt (ºC/s)')
    # ax2.set_xlim(0,tiempo_interpolado[-1])
    # ax2.set_ylim(-0.2,)

    for a in [ax,ax2]:
        a.grid()
        a.legend()
    ax.set_title('Transición de fase S-L',fontsize=18)

    # Inset 
    axin = ax.inset_axes([0.5, 0.1, 0.49, 0.45])  
    axin.plot(time_m[indx_TF], T_m[indx_TF], 'go-',label=f'T Fase: {t_tf} s')
    axin.plot(time_m, T_m, 'k-')
    axin.axhline(y=filtro_T[0], color='k',lw=1, linestyle='--')
    axin.axhline(y=filtro_T[1], color='k',lw=1, linestyle='--')
    axin.grid()
    axin.set_xlim(time_m[indx_TF[0][0]]-5,time_m[indx_TF[0][-1]]+5)
    axin.set_ylim(filtro_T[0]-0.5,filtro_T[1]+1)
    axin.legend()
    ax.indicate_inset_zoom(axin, edgecolor="black")
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(fnames_m)+'_templog_TF.png'),dpi=200,facecolor='w')

    print('Duracion de la transicion Solido/Liquido:')
    print(f'{t_tf} s')

    print('Archivos de la transicion Solido/Liquido:')
    print(f'{fnames_m[indx_TF[0][0]]} ---> {fnames_m[indx_TF[0][-1]]}')
else:
    pass
   
#%% Procesamiento en iteracion sobre archivos
'''
Ejecuto medida_cruda()
En cada iteracion levanto la info de los .txt a dataframes.
'''
k=0     #indice muestras
k_f=0   #indice fondos
for k in range(len(fnames_m)):
    if un_solo_fondo==1:
        print('Fondo unico:',fnames_f[0])
    else:
        print('1 fondo cada 3 archivos de muestra')
        if (k!=0) and (np.mod(k,3)==0):
            if k_f<len(fnames_f):
                k_f+=1
            else:
                pass
    df_m = medida_cruda_autom(path_m[k],delta_t[k])# DataFrame
    print('-'*50)
    print(k,'|')
    print('----')
    print('file:',fnames_m[k][:-4],fnames_f[k_f][:-4])
    print('path:',path_m[k][-31:-4],path_f[k_f][-31:-4])

    df_f = medida_cruda_autom(path_f[k_f],delta_t[k_f])

    '''
    Ajuste sobre señal de referencia (dH/dt) y obtengo params
    Ejecuto ajusta_seno()
    '''
    offset_m , amp_m, frec_m , fase_m = ajusta_seno(df_m['t'],df_m['v_r'])
    offset_f , amp_f, frec_f , fase_f = ajusta_seno(df_f['t'],df_f['v_r'])

    #Genero señal simulada usando params y guardo en respectivos df
    df_m['v_r_ajustada'] = sinusoide(df_m['t'],offset_m , amp_m, frec_m , fase_m)
    df_f['v_r_ajustada'] = sinusoide(df_f['t'],offset_f , amp_f, frec_f , fase_f)

    df_m['residuos'] = df_m['v_r'] - df_m['v_r_ajustada']
    df_f['residuos'] = df_f['v_r'] - df_f['v_r_ajustada']

    # Comparacion de señales y ajustes
    if graficos['Referencias_y_ajustes']==1:
        fig , ax = plt.subplots(2,1, figsize=(8,6),sharex='all')

        df_m.plot('t','v_r',label='Referencia',ax=ax[0],title=f'Muestra: {fnames_m[k]}')
        df_m.plot('t','v_r_ajustada',label='Ajuste',ax =ax[0])
        df_m.plot('t','residuos', label='Residuos',ax=ax[0])

        df_f.plot('t','v_r',label='Referencia de fondo',ax=ax[1])
        df_f.plot('t','v_r_ajustada',label='Ajuste',ax =ax[1],title=f'Fondo: {fnames_f[k_f]}')
        df_f.plot('t','residuos', label='Residuos',ax=ax[1])

        fig.suptitle('Comparacion señal de referencias y ajustes',fontsize=20)
        plt.tight_layout()

    '''
    Cortafuegos: Si la diferencia entre frecuencias es muy grande => error
    '''
    text_error ='''
    Incompatibilidad de frecuencias en:
            {:s}\n
        Muestra:              {:.3f} Hz
        Fondo:                {:.3f} Hz
        En nombre de archivo: {:.3f} Hz
    '''
    incompat = np.array([abs(frec_m-frec_f)/frec_f>0.02,abs(frec_m-frec_nombre[k])/frec_f > 0.05],dtype=bool)
    if incompat.any():
        raise Exception(text_error.format(fnames_m[k],frec_m,frec_f,frec_nombre[k_f]))
    else:
        pass

    t_m = df_m['t'].to_numpy() #Muestra
    v_m = df_m['v'].to_numpy()
    v_r_m = df_m['v_r'].to_numpy()

    '''
    Resto fondo e interpolo señal
    Ejecuto resta_inter() sobre fem de muestra
    '''
    if graficos['Resta_m-f']==1:
        Resta_m , t_m_1 , v_r_m_1 , figura_m = resta_inter(t_m,v_m,v_r_m,fase_m,frec_m,offset_m,df_f['t'],df_f['v'],df_f['v_r'],fase_f,frec_f,'muestra')
    else:
        Resta_m , t_m_1 , v_r_m_1 , figura_m = resta_inter(t_m,v_m,v_r_m,fase_m,frec_m,offset_m,df_f['t'],df_f['v'],df_f['v_r'],fase_f,frec_f,0)

    # Grafico las restas
    if graficos['Resta_mf_y_cf']==1:
        plt.figure(figsize=(10,5))
        plt.plot(t_m_1,Resta_m,'.-',lw=0.9,label='Muestra - fondo')
        # plt.plot(t_c_1,Resta_c,'.-',lw=0.9,label='Calibracion - fondo')
        plt.grid()
        plt.legend(loc='best')
        plt.title('Resta de señales')
        plt.xlabel('t (s)')
        plt.ylabel('Resta (V)')
        plt.show()
    else:
        pass
    '''
    Recorto las señales  para tener N periodos enteros
    Ejecuto recorte() sobre fem de muestra
    '''
    if graficos['Recorte_a_periodos_enteros_m']==1:
        t_m_3, v_r_m_3 , Resta_m_3, N_ciclos_m, figura_m_3 = recorte(t_m_1,v_r_m_1,Resta_m,frec_m,'muestra')
    else:
        t_m_3, v_r_m_3 , Resta_m_3, N_ciclos_m, figura_m_3 = recorte(t_m_1,v_r_m_1,Resta_m,frec_m,0)

    '''
    Ultimo ajuste sobre las señales de referencia
    Ejecuto ajusta_seno() en fem de campo
    '''
    _,amp_final_m, frec_final_m,fase_final_m = ajusta_seno(t_m_3,v_r_m_3)

    '''
    Promedio los N periodos en 1
    Ejecuto promediado_ciclos() sobre fem muestra y fem campo
    '''
    t_f_m , fem_campo_m , R_m , dt_m = promediado_ciclos(t_m_3,v_r_m_3,Resta_m_3,frec_final_m,N_ciclos_m)

    '''
    Integro los ciclos: calcula sumas acumuladas y convierte a fem a campo y magnetizacion
    La integral de la fem_campo_m es proporcional a H
    [C_norm_campo]=[A]*[1/m]+[A/m]=A/m - Cte que dimensionaliza
    al campo en A/m a partir de la calibracion realizada sobre la bobina del RF
    '''
    C_norm_campo=Idc[k]*pendiente_HvsI+ordenada_HvsI
    campo_ua0_m = dt_m*cumulative_trapezoid(fem_campo_m,initial=0) #[campo_ua0_c]=V*s
    campo_ua_m = campo_ua0_m - np.mean(campo_ua0_m) #Resto offset
    campo_m  = (campo_ua_m/max(campo_ua_m))*C_norm_campo #[campo_c]=A/m

    '''
    La integral de la fem de la muestra (c/ fondo restado),
    es proporcional a la M mas una constante'''
    magnetizacion_ua0_m = dt_m*cumulative_trapezoid(R_m,initial=0)#[magnetizacion_ua0_c]=V*s
    magnetizacion_ua_m = magnetizacion_ua0_m-np.mean(magnetizacion_ua0_m)#Resto offset

    '''
    Ajuste Lineal sobre ciclo para obtener la polaridad
    '''
    pendiente , ordenada = np.polyfit(campo_m,magnetizacion_ua_m,1) #[pendiente]=m*V*s/A  [ordenada]=V*s
    polaridad = np.sign(pendiente) # +/-1
    pendiente = pendiente*polaridad # Para que sea positiva
    magnetizacion_ua_m = magnetizacion_ua_m*polaridad  #[magnetizacion_ua_c]=V*s

    '''
    Analisis de Fourier
    Ejecuto fourier_señales_5() sobre Resta_m_3, ie la señal fem sin fondo y recortada a N ciclos

    Recupero:
        - figuras de espectros y señales
        - fem reconstruida a N armonicos impares
        - defasaje entre fems de H y M para armonico fundamental
        - frecuencia, amplitud y fase del armonico fundamental
        - Espectro (f,amp,phi) de muestra
        - Espectro (f,amp,phi) de referencia (fem de campo)
    '''
    # MOMENTO FOURIER
    if Analisis_de_Fourier == 1: 
        _, _, muestra_rec_impar,delta_phi_0,f_0,amp_0,fase_0, espectro_f_amp_fase_m,espectro_ref = fourier_señales_5(t_m_3,Resta_m_3,v_r_m_3,
                                                                                                        delta_t=delta_t[k],polaridad=polaridad,
                                                                                                        filtro=0.05,frec_limite=2*N_armonicos_impares*frec_final_m,
                                                                                                        name=fnames_m[k])

        # Guardo graficos fourier: señal/espectro y señal impar/espectro filtrado
        output_dir_espectros= os.path.join(output_dir,'espectros_reconstrucciones')
        if not os.path.exists(output_dir_espectros):# Crear el subdirectorio si no existe
            os.makedirs(output_dir_espectros)
        
        # fig_fourier.savefig(os.path.join(output_dir_espectros,fnames_m[k]+'_Espectro.png'),dpi=200,facecolor='w')
        # fig2_fourier.savefig(os.path.join(output_dir_espectros,fnames_m[k]+'_Rec_impar.png'),dpi=200,facecolor='w')

        print(f'\nf0 campo: {espectro_ref[0]:.2f} Hz')
        print(f'\nf0 muestra: {f_0:.2f} Hz')
        print(f'Delta t: {(t_m_3[-1]-t_m_3[0]):.2e}')
        print(f'N de periodos enteros: {N_ciclos_m}')
        print(f'Num de puntos de la seña: {len(Resta_m_3)}')

        #CALCULO SAR
        Hmax=max(campo_m)
        N = len(Resta_m_3)
        sar = mu_0*Hmax*(amp_0*C_Vs_to_Am_magnetizacion)*np.sin(delta_phi_0)/(concentracion*N)
        
        print(f'\nSAR: {sar:.2f} (W/g)')
        print(f'Concentracion: {concentracion/1000} g/L')
        print(f'Fecha de la medida: {fecha_m[k]}')
        print('-'*50)
        # TAU a partir de la FASE
        tau=np.tan(delta_phi_0)/(2*np.pi*frec_final_m)

        # Hasta aca lo que tiene que ver con analisis armonico
        '''
        Reemplazo señal recortada con la filtrada en armonicos impares:
            Resta_m_3 ==> muestra_rec_impar
        Ejecuto promediado_ciclos() sobre muestra_rec_impar
        '''
        t_f_m , fem_campo_m , fem_mag_m , dt_m = promediado_ciclos(t_m_3,v_r_m_3,muestra_rec_impar,frec_final_m,N_ciclos_m)

        magnetizacion_ua0_m_filtrada = dt_m*cumulative_trapezoid(fem_mag_m,initial=0)
        magnetizacion_ua_m_filtrada = magnetizacion_ua0_m_filtrada-np.mean(magnetizacion_ua0_m_filtrada)

    else:
        #Sin analisis de Fourier, solamente acomodo la polaridad de la señal de la muestra.
        t_f_m , fem_campo_m , fem_mag_m , dt_m = promediado_ciclos(t_m_3,v_r_m_3,Resta_m_3*polaridad,frec_final_m,N_ciclos_m)
    
    '''
    Asigno unidades a la magnetizacion utilizando la calibracion que esta al principio del script
    '''
    magnetizacion_m = C_Vs_to_Am_magnetizacion*magnetizacion_ua_m #[magnetizacion_m]=A/m
    magnetizacion_m_filtrada = C_Vs_to_Am_magnetizacion*magnetizacion_ua_m_filtrada #[magnetizacion_m_filtrada]=A/m
    
    magnetizacion_m_des = magnetizacion_m + 2*abs(min(magnetizacion_m))
    Area_ciclo = abs(trapezoid(magnetizacion_m_des,campo_m)) 
    sar_area =  mu_0*Area_ciclo*frec_final_m/(concentracion)  #[sar]=[N/A^2]*[A^2/m^2]*[1/s]*[m^3/g]=W/g
    print(f'\nSAR area: {sar_area:.2f} (W/g)')
    '''
    Ploteo H(t) y M(t) normalizados
    '''
    if graficos['Campo_y_Mag_norm_m']==1:
        fig , ax =plt.subplots(figsize=(8,5),constrained_layout=True)
        ax.plot(t_f_m,campo_m/max(campo_m),'tab:red',label='H')
        ax.plot(t_f_m,magnetizacion_m/max(magnetizacion_m_filtrada),label='M')
        ax.plot(t_f_m,magnetizacion_m_filtrada/max(magnetizacion_m_filtrada),label='M filt impares')
        plt.xlim(0,t_f_m[-1])
        plt.legend(loc='best',ncol=2)
        plt.grid()
        plt.xlabel('t (s)')
        plt.title('Campo y magnetización normalizados de la muestra\n'+fnames_m[k][:-4])
        plt.savefig(os.path.join(output_dir,os.path.commonprefix(fnames_m),'_H_M_norm.png'),dpi=200,facecolor='w')
    '''
    Campo Coercitivo (Hc) y Magnetizacion Remanente (Mr)
    '''
    m = magnetizacion_m
    m_filt = magnetizacion_m_filtrada
    h = campo_m
    Hc = []
    Mr = []

    for z in range(0,len(m)-1):
        if ((m_filt[z]>0 and m_filt[z+1]<0) or (m_filt[z]<0 and m_filt[z+1]>0)): #M remanente
            Hc.append(abs(h[z] - m_filt[z]*(h[z+1] - h[z])/(m_filt[z+1]-m_filt[z])))

        if((h[z]>0 and h[z+1]<0) or (h[z]<0 and h[z+1]>0)):  #H coercitivo
            Mr.append(abs(m_filt[z] - h[z]*(m_filt[z+1] - m_filt[z])/(h[z+1]-h[z])))

    Hc_mean = np.mean(Hc)
    Hc_mean_kAm = Hc_mean/1000
    Hc_error = np.std(Hc)
    Mr_mean = np.mean(Mr)
    Mr_mean_kAm = Mr_mean/1000
    Mr_error = np.std(Mr)
    print(f'\nHc = {Hc_mean:.2f} (+/-) {Hc_error:.2f} (A/m)')
    print(f'Mr = {Mr_mean:.2f} (+/-) {Mr_error:.2f} (A/m)')
    
    '''
    Ploteo ciclo de histeresis individual
    '''
    if graficos['Ciclo_HM_m']==1:
        
        cmap = mpl.colormaps['viridis']
        norm = plt.Normalize(temp_m.min(), temp_m.max())# Crear un rango de colores basado en las temperaturas y el cmap
        color = cmap(norm(temp_m[k]))
        output_dir_ciclos= os.path.join(output_dir,'ciclos_H_M')
        if not os.path.exists(output_dir_ciclos):# Crear el subdirectorio si no existe
            os.makedirs(output_dir_ciclos)
            
        fig , ax =plt.subplots(figsize=(7,5.5), constrained_layout=True)
        ax.plot(campo_m,magnetizacion_m,'.-',label=f'{fnames_m[k].split("_")[-1].split(".txt")[0][5:]}')
        ax.plot(campo_m,magnetizacion_m_filtrada,color=color,label=f'{fnames_m[k].split("_")[-1].split(".txt")[0][5:]} ({N_armonicos_impares} armónicos)')
        ax.scatter(0,Mr_mean,marker='s',c='tab:orange',label=f'M$_r$ = {Mr_mean:.0f} A/m')
        ax.scatter(Hc_mean,0,marker='s',c='tab:orange',label=f'H$_c$ = {Hc_mean:.0f} A/m')
        # ax.plot(campo_m,magnetizacion_m_filtrada_fase,label='Muestra filtrada s/fase')
        plt.legend(loc='best')
        plt.grid()
        plt.xlabel('H $(A/m)$')
        plt.ylabel('M $(A/m)$')
        plt.title('Ciclo de histéresis de la muestra\n'+fnames_m[k][:-4])
        plt.text(0.75,0.25,f'T = {temp_m[k]} °C\nSAR = {sar:0.1f} W/g',fontsize=13,bbox=dict(color='tab:red',alpha=0.6),
                 va='center',ha='center',transform=ax.transAxes)
        plt.savefig(os.path.join(output_dir_ciclos,fnames_m[k][:-4])+'_ciclo_H_M.png',dpi=200,facecolor='w')
        plt.close(fig)
    # Xi Susceptibilidad a M=0 (excepto ultimo archivo que es el control de descancelacion)
    if k != len(fnames_m):
        if graficos['Susceptibilidad_M_0']==1:
            try:
                susc_a_M_0=susceptibilidad_M_0(campo_m,magnetizacion_m_filtrada,fnames_m[k][:-4],Hc_mean)
            except UnboundLocalError:
                print('Error al determinar el cruce por M=0')
                susc_a_M_0=0
        else:
            try:
                susc_a_M_0=susceptibilidad_M_0(campo_m,magnetizacion_m_filtrada,fnames_m[k][:-4],Hc_mean)
            except UnboundLocalError:
                print('Error al determinar el cruce por M=0')
                susc_a_M_0=0
    '''
    Lleno listas de resultados,
    al salir del loop miro que la Mmax de
    1eros/ultimos 10 files no sea demasiado baja de la media
    Despues filtro, asi no exporto al pedo
    '''

    #Ajuste sobre señales de referencia
    Frecuencia_ref_muestra_kHz.append(frec_final_m/1000)#Frecuencia de la referencia en la medida de la muestra
    Frecuencia_ref_fondo_kHz.append(frec_f/1000)        #Frecuencia de la referencia en la medida del fondo

    #Analisis armonico
    long_arrays.append(len(Resta_m_3))
    Frec_fund.append(f_0)
    Magnitud_1er_arm.append(amp_0)
    Defasaje_1er_arm.append(delta_phi_0)
    Tau.append(tau)                                 #Calculado con magnitud y defasaje
    SAR.append(sar)                                 #Calculado con magnitud y defasaje
    SAR_area.append(sar_area)
    
    # cociente_f1_f0.append(espectro_f_amp_fase_m[1][1]/espectro_f_amp_fase_m[1][0])
    # cociente_f2_f0.append(espectro_f_amp_fase_m[1][2]/espectro_f_amp_fase_m[1][0])

    #Reconstruccion impar, integracion
    Ciclos_tiempo.append(t_f_m[:] - t_f_m[0])
    Ciclos_eje_H_ua.append(campo_ua_m)
    Ciclos_eje_M_ua.append(magnetizacion_ua_m)
    Ciclos_eje_H.append(campo_m)
    Ciclos_eje_M.append(magnetizacion_m)
    Ciclos_eje_M_filt.append(magnetizacion_m_filtrada)
    Campo_maximo.append(Hmax)                       #Campo maximo en A/m
    Mag_max.append(max(magnetizacion_m_filtrada))   #Magnetizacion maxima
    Coercitividad_kAm.append(Hc_mean/1000)          #Campo coercitivo en kA/m
    Remanencia_Am.append(Mr_mean)                   #Magnetizacion remanente en kA/m
    xi_M_0.append(susc_a_M_0)                       #Sin unidades

    # #% EXPORTO CICLOS HM
    # '''
    # Exporto ciclos de histeresis en ASCII, primero en V.s, despues en A/m :
    # | Tiempo (s) | Campo (V.s) | Magnetizacion (V.s) | Campo (A/m) |  Magnetizacion (A/m)
    # '''
    # col0 = t_f_m - t_f_m[0]
    # col1 = campo_ua_m
    # col2 = magnetizacion_ua_m
    # col3 = campo_m/1000 #kA/m
    # col4 = magnetizacion_m_filtrada#A/m

    # ciclo_out = Table([col0, col1, col2,col3,col4])

    # encabezado = ['Tiempo_(s)','Campo_(V.s)', 'Magnetizacion_(V.s)','Campo_(kA/m)', 'Magnetizacion_(A/m)']
    # formato = {'Tiempo_(s)':'%e' ,'Campo_(V.s)':'%e','Magnetizacion_(V.s)':'%e','Campo_(kA/m)':'%e','Magnetizacion_(A/m)':'%e'}

    # ciclo_out.meta['comments'] = [f'Temperatura_=_{temp_m[k]}',
    #                               f'Concentracion g/m^3_=_{concentracion}',
    #                               f'C_Vs_to_Am_M_A/Vsm_=_{C_Vs_to_Am_magnetizacion}',
    #                               f'pendiente_HvsI_1/m_=_{pendiente_HvsI}',
    #                               f'ordenada_HvsI_A/m_=_{ordenada_HvsI}',
    #                               f'frecuencia_Hz_=_{frec_final_m}\n']

    # output_file = os.path.join(output_dir, fnames_m[k][:-4] + '_ciclo_H_M.txt')
    # ascii.write(ciclo_out,output_file,names=encabezado,overwrite=True,delimiter='\t',formats=formato)

    plt.close('all')
#%% DETECTOR CICLOS DESCARTABLES
fnames_m=np.array(fnames_m)

if detector_ciclos_descartables:
    archivos_in_out=7
    porcentaje_diferencia=40#%
    print(f'Se identifican archivos cuya Mag maxima difieren un {porcentaje_diferencia}% de la')
    print(f'Mag max promedio = {np.mean(Mag_max[archivos_in_out:-archivos_in_out]):.0f}({np.std(Mag_max[archivos_in_out:-archivos_in_out]):.0f}) A/m de los {len(Mag_max[archivos_in_out:-archivos_in_out])} valores centrales.')

    indx_discard = np.nonzero((Mag_max[:-1]>(1+porcentaje_diferencia/100)*np.mean(Mag_max[archivos_in_out:-archivos_in_out])) | (Mag_max[:-1]<(1-porcentaje_diferencia/100)*np.mean(Mag_max[archivos_in_out:-archivos_in_out])))[0]
    for ind in indx_discard:
        print(' ->',fnames_m[ind])

    print(f'\nDescartamos {len(indx_discard)} archivos de un total de {len(fnames_m)}.')
    print(f'\nArchivo {fnames_f[0]} identificado como Fondo.')
    print(f'Archivo {fnames_m[-1]} identificado como Descancelacion.')

    # Muevo archivos decartados
    # Directorio de destino
    # output_dir_ciclos_descartados= os.path.join(output_dir,'ciclos_descartados')
    # if not os.path.exists(output_dir_ciclos_descartados):# Crear el subdirectorio si no existe
    #     os.makedirs(output_dir_ciclos_descartados)

    # files_to_move=[fnames_m[f] for f  in indx_discard]
    # filepaths_to_move=[path_m[f] for f  in indx_discard]
    # # Mover archivos al subdirectorio
    # for fp in filepaths_to_move:
    #     shutil.copy(fp, output_dir_ciclos_descartados)
    #     #print(f"Copied {fp.split('/')[-1]} to {output_dir_ciclos_descartados}")
    indices_to_stay = np.setdiff1d(np.arange(len(fnames_m)-1), indx_discard)

else:
    print('\nNo se descartó automaticamente ningun ciclo')
    

#%% PLOTEO TODOS LOS CICLOS RAW

cmap = mpl.colormaps['viridis']
norm = plt.Normalize(temp_m.min(), temp_m.max())# Crear un rango de colores basado en las temperaturas y el cmap
if graficos['Ciclos_HM_m_todos']==1:
    fig = plt.figure(figsize=(9,7),constrained_layout=True)
    ax = fig.add_subplot(1,1,1)
    if detector_ciclos_descartables:
        for i in indx_discard: #Ciclos in
            plt.plot(Ciclos_eje_H[i]/1000,Ciclos_eje_M[i],'.',label=f'{fnames_m[i].split("_")[-1].split(".")[0]:<4s}',alpha=0.5)

        for i in indices_to_stay[:-1]: #Ciclos aceptados
            color = cmap(norm(temp_m[i]))
            plt.plot(Ciclos_eje_H[i]/1000,Ciclos_eje_M[i],color=color)
    else:
        for i in range(len(fnames_m[:-1])): #Ciclos aceptados
            color = cmap(norm(temp_m[i]))
            plt.plot(Ciclos_eje_H[i]/1000,Ciclos_eje_M[i],color=color)
        
    
    plt.plot(Ciclos_eje_H[-1]/1000,Ciclos_eje_M[-1],'-',color='k') #Descancelacion

plt.legend(title='Ciclos descartados',ncol=2,loc='best',fancybox=True)

# # Configurar la barra de colores
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])  # Esto es necesario para que la barra de colores muestre los valores correctos
plt.colorbar(sm, label='Temperatura',ax=ax)  # Agrega una etiqueta adecuada
#lt.text(0.15,0.75,,fontsize=20,bbox=dict(color='tab:orange',alpha=0.7),transform=ax.transAxes)
plt.grid()
plt.xlabel('H (kA/m)',fontsize=15)
plt.ylabel('M (A/m)',fontsize=15)
plt.suptitle('Ciclos de histéresis (sin filtrar)',fontsize=20)
plt.title(f'{frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m',loc='center',fontsize=15)
plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_ciclos_MH_raw.png'),dpi=300,facecolor='w')

#%% RECORTO LISTAS

fnames_m = fnames_m[indices_to_stay]
temp_m = np.array([temp_m[i] for i in indices_to_stay])
if templog:
    time_m=[time_m[i] for i in indices_to_stay]
else:
    time_m=np.arange(len(fnames_m))
Fechas_from_file_m=[Fechas_from_file[i] for i in indices_to_stay]

Ciclo_descancelacion_H=Ciclos_eje_H[-1]
Ciclo_descancelacion_M=Ciclos_eje_M[-1]
Ciclo_descancelacion_M_filt=Ciclos_eje_M_filt[-1]

Ciclos_eje_H=[Ciclos_eje_H[i] for i in indices_to_stay]
Ciclos_eje_M=[Ciclos_eje_M[i] for i in indices_to_stay]
Ciclos_eje_M_filt=[Ciclos_eje_M_filt[i] for i in indices_to_stay]

Remanencia_Am=[Remanencia_Am[i] for i in indices_to_stay]
Coercitividad_kAm=[Coercitividad_kAm[i] for i in indices_to_stay]
Campo_maximo=[Campo_maximo[i] for i in indices_to_stay]
Mag_max=[Mag_max[i] for i in indices_to_stay]
Frec_fund=[Frec_fund[i] for i in indices_to_stay]
Magnitud_1er_arm=[Magnitud_1er_arm[i] for i in indices_to_stay]
Defasaje_1er_arm=[Defasaje_1er_arm[i] for i in indices_to_stay]
SAR=[SAR[i] for i in indices_to_stay]
SAR_area=[SAR_area[i] for i in indices_to_stay]
    

Tau=[Tau[i]*1e9 for i in indices_to_stay] #paso a ns
xi_M_0=[xi_M_0[i] for i in indices_to_stay]
# cociente_f1_f0=[cociente_f1_f0[i] for i in indices_to_stay]
# cociente_f2_f0=[cociente_f2_f0[i] for i in indices_to_stay]
long_arrays=[long_arrays[i] for i in indices_to_stay]
#%% CICLO PROMEDIO
if Ciclo_promedio:
    min_len_t = min([len(f) for f in Ciclos_tiempo])
    min_len_H_ua=min([len(f) for f in Ciclos_eje_H_ua])
    min_len_M_ua=min([len(f) for f in Ciclos_eje_M_ua])
    min_len_H=min([len(f) for f in Ciclos_eje_H])
    min_len_M=min([len(f) for f in Ciclos_eje_M])

    t0=Ciclos_tiempo[0][:min_len_t]
    H0_ua=Ciclos_eje_H_ua[0][:min_len_H_ua]
    M0_ua=Ciclos_eje_M_ua[0][:min_len_M_ua]
    H0=Ciclos_eje_H[0][:min_len_H]
    M0=Ciclos_eje_M_filt[0][:min_len_M]

    for i in range(1,len(fnames_m)):

        t0=t0 + Ciclos_tiempo[i][:min_len_t]
        H0_ua=H0_ua+ Ciclos_eje_H_ua[i][:min_len_H_ua]
        M0_ua=M0_ua+ Ciclos_eje_M_ua[i][:min_len_M_ua]
        H0=H0+Ciclos_eje_H[i][:min_len_H]
        M0=M0+Ciclos_eje_M_filt[i][:min_len_M]

        Num_ciclos_m=len(fnames_m)

        t_prom= t0/Num_ciclos_m
        H_prom_ua=H0_ua/Num_ciclos_m
        M_prom_ua=M0_ua/Num_ciclos_m
        H_prom=H0/Num_ciclos_m
        M_prom=M0/Num_ciclos_m
    
    # Encontrar la longitud mínima
    min_length = min(len(vec) for vec in [t_prom,H_prom_ua,M_prom_ua,H_prom,M_prom])

    # Recortar todos los vectores a la longitud mínima
    t_prom = t_prom[:min_length]
    H_prom_ua = H_prom_ua[:min_length]
    M_prom_ua = M_prom_ua[:min_length]
    H_prom = H_prom[:min_length]
    M_prom = M_prom[:min_length]
        
        
    # '''
    # Exporto ciclos promedio en ASCII, primero en V.s, despues en A/m :
    # | Tiempo (s) | Campo (V.s) | Magnetizacion (V.s) | Campo (A/m) |  Magnetizacion (A/m)
    # '''
    ciclo_out = Table([t_prom,H_prom_ua/1e3,M_prom_ua,H_prom/1e3,M_prom])

    encabezado = ['Tiempo_(s)','Campo_(V.s)', 'Magnetizacion_(V.s)','Campo_(kA/m)', 'Magnetizacion_(A/m)']
    formato = {'Tiempo_(s)':'%e' ,'Campo_(V.s)':'%e','Magnetizacion_(V.s)':'%e','Campo_(kA/m)':'%e','Magnetizacion_(A/m)':'%e'}


    ciclo_out.meta['comments'] = [f'Temperatura_=_{np.mean(temp_m)}',
                                    f'Concentracion g/m^3_=_{concentracion}',
                                    f'C_Vs_to_Am_M_A/Vsm_=_{C_Vs_to_Am_magnetizacion}',
                                    f'pendiente_HvsI_1/m_=_{pendiente_HvsI}',
                                    f'ordenada_HvsI_A/m_=_{ordenada_HvsI}',
                                    f'frecuencia_Hz_=_{frec_final_m}',
                                    f'Promedio de {Num_ciclos_m} ciclos\n']

    output_file = os.path.join(output_dir, os.path.commonprefix(list(fnames_m)) + '_ciclo_promedio_H_M.txt')# Especificar la ruta completa del archivo de salida
    ascii.write(ciclo_out,output_file,names=encabezado,overwrite=True,delimiter='\t',formats=formato)
else:
    pass
#%%#%% GUARDO RESULTADOS.TXT
'''
Guardo ASCII con los datos de todo el procesamiento:
    |fname|time|Temp|Mr|Hc|Hmax|Mmax|f0|mag0|phi0|dphi0|SAR|Tau|N|xi_M_0|
'''
SAR_all = ufloat(np.mean(SAR),np.std(SAR))
defasaje_all= ufloat(np.mean(Defasaje_1er_arm),np.std(Defasaje_1er_arm))
Coercitividad_all = ufloat(np.mean(Coercitividad_kAm),np.std(Coercitividad_kAm))
Remanencia_all = ufloat(np.mean(Remanencia_Am),np.std(Remanencia_Am))
xi_all = ufloat(np.mean(xi_M_0),np.std(xi_M_0))
tau_all= ufloat(np.mean(Tau),np.std(Tau))
Mag_max_all=ufloat(np.mean(Mag_max),np.std(Mag_max))
Mag_max_emu = Mag_max_all/(concentracion/1000)
if templog:
    col1 = time_m

else:
    col1= np.zeros_like(fnames_m)

col0 = fnames_m
col2 = temp_m
col3 = Remanencia_Am
col4 = Coercitividad_kAm
col5 = Campo_maximo
col5_bis = Mag_max
col6 = Frec_fund
col7 = Magnitud_1er_arm
col8 = Defasaje_1er_arm
col9 = SAR
col10 = Tau
col11 = long_arrays
col12 = xi_M_0
resultados_out=Table([col0, col1,col2,col3,col4,col5,col5_bis,col6,col7,col8,col9,col10,col11,col12])
encabezado = ['Nombre_archivo','Time_m_(s)','Temperatura_(ºC)','Mr_(A/m)','Hc_(kA/m)',
              'Campo_max_(A/m)','Mag_max_(A/m)','f0','mag0','dphi0','SAR_(W/g)','Tau_(ns)','N','xi_M_0']

formato = {'Nombre_archivo':'%s' ,'Time_m_(s)':'%s','Temperatura_(ºC)':'%.2f',
           'Mr_(A/m)':'%.2f','Hc_(kA/m)':'%.2f','Campo_max_(A/m)':'%.2f',
           'Mag_max_(A/m)':'%.2f','f0':'%e','mag0':'%e','dphi0':'%e',
           'SAR_(W/g)':'%.2f','Tau_(ns)':'%f','N':'%.0f','xi_M_0':'%.3e'}

if Transicion_de_fase:
    resultados_out.meta['comments'] = ['Configuracion:',
                              f'Concentracion g/m^3_=_{concentracion}',
                              f'C_Vs_to_Am_M_A/Vsm_=_{C_Vs_to_Am_magnetizacion}',
                              f'pendiente_HvsI_1/m_=_{pendiente_HvsI}',
                              f'ordenada_HvsI_A/m_=_{ordenada_HvsI}',
                              f'frecuencia_ref_Hz_=_{frec_final_m}',
                              '\nResultados:',
                              f'tau_s_=_{tau_all:.2e}',
                              f'dphi_rad_=_{defasaje_all:.2f}',
                              f'SAR_W/g_=_{SAR_all:.2f}',
                              f'Hc_kA/m_=_{Coercitividad_all:.2f}',
                              f'Mr_A/m_=_{Remanencia_all:.2f}',
                              f'Suceptibilidad_a_M=0_=_{xi_all:.4f}',
                              f'Magnetizacion_max_emu/g_=_{Mag_max_emu}',
                              f't_hasta_1er_file_=_{delta_0:.2f}',
                              f'Duracion_T_Fase_=_{t_tf}',
                              f'1er_file_T_Fase_=_{fnames_m[indx_TF[0][0]]}',
                              f'last_file_T_Fase_=_{fnames_m[indx_TF[0][-1]]}\n']

else:
    resultados_out.meta['comments'] = ['Configuracion:',
                              f'Concentracion g/m^3_=_{concentracion}',
                              f'C_Vs_to_Am_M_A/Vsm_=_{C_Vs_to_Am_magnetizacion}',
                              f'pendiente_HvsI_1/m_=_{pendiente_HvsI}',
                              f'ordenada_HvsI_A/m_=_{ordenada_HvsI}',
                              f'frecuencia_ref_Hz_=_{frec_final_m}',
                              '\nResultados:',
                              f'tau_ns_=_{tau_all:.2e}',
                              f'dphi_rad_=_{defasaje_all:.2f}',
                              f'SAR_W/g_=_{SAR_all:.2f}',
                              f'Hc_kA/m_=_{Coercitividad_all:.2f}',
                              f'Mr_A/m_=_{Remanencia_all:.2f}',
                              f'Magnetizacion_max_emu/g_=_{Mag_max_emu}',
                              f'Suceptibilidad_a_M=0_=_{xi_all:.3e}\n']



output_file2=os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_resultados.txt')
ascii.write(resultados_out,output_file2,names=encabezado,overwrite=True,delimiter='\t',formats=formato)

#guardo SAR x area
np.savetxt(os.path.join(output_dir,'SAR_area.txt'),np.array(SAR_area),fmt='%e' )
#%% PLOTEO TODOS LOS CICLOS FILTRADOS IMPAR
cmap = mpl.colormaps['turbo']
norm = plt.Normalize(temp_m.min(), temp_m.max())# Crear un rango de colores basado en las temperaturas y el cmap

cuadro_1= fr'$\tau$ = {tau_all:.0f} ns'+f'\nSAR = {SAR_all:.0f} W/g\nH$_c$ = {Coercitividad_all:.1f} kA/m\nM$_r$ = {Remanencia_all:.1f} A/m'+'\nM$_{max}$'+f' = {Mag_max_emu:.1f}'+r' $\frac{emu}{g}$'

 
if Analisis_de_Fourier==1:
    fig = plt.figure(figsize=(9,7),constrained_layout=True)
    ax = fig.add_subplot(1,1,1)
    for i in range(len(fnames_m)):
            color = cmap(norm(temp_m[i]))
            plt.plot(Ciclos_eje_H[i]/1000,Ciclos_eje_M_filt[i],'-',color=color)


    plt.plot(Ciclo_descancelacion_H/1000,Ciclo_descancelacion_M_filt,'-',color='k',label='Descancelación')
    plt.plot(Ciclos_eje_H[0]/1000,Ciclos_eje_M_filt[0],'--',lw=2.2,color='tab:blue',label=f'{fnames_m[0].split("_")[-1][-7:-4]}  {temp_m[0]} °C')
    plt.plot(Ciclos_eje_H[-1]/1000,Ciclos_eje_M_filt[-1],'--',lw=2.2,color='tab:orange',label=f'{fnames_m[-1].split("_")[-1][-7:-4]}  {temp_m[-1]} °C')
    
    if Ciclo_promedio:
        plt.plot(H_prom/1000,M_prom,'-.',c='tab:red',label=f'Ciclo promedio ({Num_ciclos_m} ciclos)')
plt.legend(loc='lower right',fancybox=True,ncol=2)

# Configurar la barra de colores
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])  # Esto es necesario para que la barra de colores muestre los valores correctos
plt.colorbar(sm, label='Temperatura', ax=ax)  # Agrega una etiqueta adecuada


plt.text(0.8,0.20,cuadro_1,
         fontsize=14,bbox=dict(color='tab:green',alpha=0.7),transform=ax.transAxes,ha='center')

plt.text(0.25,0.75,f'{frec_nombre[0]/1000:>3.0f} kHz\n{round(np.mean(Campo_maximo)/1e3,2):>4.2f} kA/m',
         fontsize=20,bbox=dict(color='tab:orange',alpha=0.7),transform=ax.transAxes,ha='center')
plt.grid()
plt.xlabel('H (kA/m)',fontsize=15)
plt.ylabel('M (A/m)',fontsize=15)
plt.title(fecha_graf + f'   {N_armonicos_impares} arm impares',loc='left',fontsize=13)
plt.suptitle('Ciclos de histéresis (filtrado impar)',fontsize=20)
plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_ciclos_MH.png'),dpi=300,facecolor='w')
# plt.show()

#%% PLOTEO TODOS LOS CICLOS FILTRADOS de la TRANSICION DE FASE
if Transicion_de_fase==1:
    cmap = mpl.colormaps['jet']
    norm2 = plt.Normalize(temp_m[indx_TF[0][0]], temp_m[indx_TF[0][-1]])# Crear un rango de colores basado en las temperaturas y el cmap

    if Analisis_de_Fourier==1:
        fig = plt.figure(figsize=(9,7),constrained_layout=True)
        ax = fig.add_subplot(1,1,1)
        for i in range(indx_TF[0][0],indx_TF[0][-1]):
                color = cmap(norm2(temp_m[i]))
                plt.plot(Ciclos_eje_H[i]/1000,Ciclos_eje_M_filt[i],'-',lw=2,color=color)

        # plt.plot(Ciclo_descancelacion_H/1000,Ciclo_descancelacion_M_filt,'-',color='k',label='Descancelación')
        # plt.plot(Ciclos_eje_H[0]/1000,Ciclos_eje_M_filt[0],'.-',color='tab:blue',label=f'{fnames_m[0].split("_")[-1][-7:-4]}  {temp_m[0]} °C')
        # plt.plot(Ciclos_eje_H[-1]/1000,Ciclos_eje_M_filt[-1],'.-',color='tab:orange',label=f'{fnames_m[-1].split("_")[-1][-7:-4]}  {temp_m[-1]} °C')

        #plt.plot(H_prom/1000,M_prom,'.-',label=f'Ciclo promedio ({Num_ciclos_m} ciclos)')
    #plt.legend(loc='lower right',fancybox=True)

    # Configurar la barra de colores
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm2)
    sm.set_array([])  # Esto es necesario para que la barra de colores muestre los valores correctos
    plt.colorbar(sm, label='Temperatura', ax=ax)  # Agrega una etiqueta adecuada

    plt.grid()
    plt.text(0.10,0.80,f'{frec_nombre[0]/1000:>3.0f} kHz\n{round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m',fontsize=20,bbox=dict(color='tab:orange',alpha=0.7),transform=ax.transAxes)
    plt.xlabel('H (kA/m)',fontsize=15)
    plt.ylabel('M (A/m)',fontsize=15)
    plt.title(f'{fnames_m[indx_TF[0][0]]} --> {fnames_m[indx_TF[0][-1]]}',loc='left',fontsize=12)
    plt.suptitle('Ciclos de histéresis en transicón de fase',fontsize=18)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_ciclos_MH_TF.png'),dpi=300,facecolor='w')
    # plt.show()
else:
    print('\nNo se requiere calculo de transicion de fase.')


#%% tau/SAR vs Temperatura or tau/SAR vs indx
if templog:
    # Definir el mapa de colores (jet en este caso)
    cmap = mpl.colormaps['jet'] #'viridis'
    # Normalizar las temperaturas al rango [0, 1] para obtener colores
    normalized_temperaturas = (np.array(temp_m) - np.array(temp_m).min()) / (np.array(temp_m).max() - np.array(temp_m).min())
    # Obtener los colores correspondientes a las temperaturas normalizadas
    colors = cmap(normalized_temperaturas)

    fig, ax = plt.subplots(2, 1, figsize=(10,5), constrained_layout=True,sharex=True)
    ax[0].scatter(temp_m, Tau,c=colors, marker='o', label=r'$\tau$')
    ax[0].plot(temp_m, Tau,zorder=-1)
    ax[0].set_ylabel(r'$\tau$ (s)')

    ax[1].scatter(temp_m, SAR,c=colors,marker= 'o', label=f'{concentracion/1000:.2f} g/L')
    ax[1].plot(temp_m, SAR,zorder=-1)
    ax[1].set_xlabel('T (°C)')
    ax[1].set_ylabel('SAR (W/g)')

    for a in ax:
        # a.axvspan(temperatura_interpolada[indx_TF_interp[0][0]],temperatura_interpolada[indx_TF_interp[0][-1]],color='tab:red',alpha=0.4,label=f'T Fase: {t_tf} s',zorder=-2)
        a.legend(ncol=2)
        a.grid()

    ax[0].set_title(f'\n{nombre.strip("*")} - {frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m')
    plt.suptitle(r'$\tau$ - SAR',fontsize=15)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_tau_SAR_vs_T.png'),dpi=300,facecolor='w')

    #% tau & SAR vs tiempo
    fig, ax = plt.subplots(2, 1, figsize=(10,6), constrained_layout=True,sharex=True)
    ax[0].scatter(time_m, Tau,c=colors, marker='o', label=r'$\tau$')
    ax[0].plot(time_m, Tau,zorder=-1)
    ax[0].set_ylabel(r'$\tau$ (ns)')

    ax[1].scatter(time_m, SAR,c=colors,marker= 'o', label=f'C = {concentracion/1000:.2f} g/L')
    ax[1].plot(time_m, SAR,zorder=-1)
    ax[1].set_xlabel('t (s)')
    ax[1].set_ylabel('SAR (W/g)')

    for a in ax:
        # a.axvspan(tiempo_interpolado[indx_TF_interp[0][0]],tiempo_interpolado[indx_TF_interp[0][-1]],color='tab:red',alpha=0.5,label=f'T Fase: {t_tf} s',zorder=-2)
        a.legend(ncol=2)
        a.grid()
    ax[0].set_title(f'\n{nombre.strip("*")} - {frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m')
    plt.suptitle(r'$\tau$ - SAR',fontsize=15)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_tau_SAR_vs_tiempo.png'),dpi=300,facecolor='w')

    #% Hc & Mr & xi vs T
    fig, ax = plt.subplots(3, 1, figsize=(9,7), constrained_layout=True,sharex=True)
    ax[0].scatter(temp_m,Coercitividad_kAm,c=colors, marker='o',label='H$_C$')
    ax[0].plot(temp_m,Coercitividad_kAm,zorder=-1)
    ax[0].set_ylabel('Campo Coercitivo (kA/m)')

    ax[1].scatter(temp_m, xi_M_0,c=colors, marker='s',label='$\chi$ a M=0')
    ax[1].plot(temp_m, xi_M_0,zorder=-1)
    ax[1].set_ylabel('Susceptibilidad a M=0')

    ax[2].scatter(temp_m, Remanencia_Am,c=colors, marker='D',label='M$_R$')
    ax[2].plot(temp_m, Remanencia_Am,zorder=-1)
    ax[2].set_ylabel('Magnetizacion Remanente')
    ax[2].set_xlabel('T (°C)')

    for a in ax:
        # a.axvspan(temperatura_interpolada[indx_TF_interp[0][0]],temperatura_interpolada[indx_TF_interp[0][-1]],color='tab:red',alpha=0.4,label=f'T Fase: {t_tf} s',zorder=-2)
        a.legend(ncol=2)
        a.grid()

    ax[0].set_title(f'\n{nombre.strip("*")} - {frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m')
    plt.suptitle(r'H$_C$ - M$_R$ - $\chi_{M=0}$',fontsize=15)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_Hc_Mr_xi_vs_T.png'),dpi=300,facecolor='w')
    #% Hc & Mr & xi vs tiempo

    fig, ax = plt.subplots(3, 1, figsize=(9,7), constrained_layout=True,sharex=True)
    ax[0].scatter(time_m,Coercitividad_kAm,c=colors, marker='o',label='H$_C$')
    ax[0].plot(time_m,Coercitividad_kAm,zorder=-1)
    ax[0].set_ylabel('Campo Coercitivo (kA/m)')

    ax[1].scatter(time_m, xi_M_0,c=colors, marker='s',label='$\chi$ a M=0')
    ax[1].plot(time_m, xi_M_0,zorder=-1)
    ax[1].set_ylabel('Susceptibilidad a M=0')

    ax[2].scatter(time_m, Remanencia_Am,c=colors, marker='D',label='M$_R$')
    ax[2].plot(time_m, Remanencia_Am,zorder=-1)
    ax[2].set_ylabel('Magnetizacion Remanente')
    ax[2].set_xlabel('t (s)')

    for a in ax:
        # a.axvspan(tiempo_interpolado[indx_TF_interp[0][0]],tiempo_interpolado[indx_TF_interp[0][-1]],color='tab:red',alpha=0.5,label=f'T Fase: {t_tf} s',zorder=-2)
        a.legend(ncol=2)
        a.grid()
        
    ax[0].set_title(f'\n{nombre.strip("*")} - {frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m')
    plt.suptitle(r'H$_C$ - M$_R$ - $\chi_{M=0}$',fontsize=15)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_Hc_Mr_xi_vs_T.png'),dpi=300,facecolor='w')

else:
    # Tau, SAR
    fig, ax = plt.subplots(2, 1, figsize=(10,5), constrained_layout=True,sharex=True)
    ax[0].plot(np.arange(len(Tau)), Tau,'o-',label=r'$\tau$')
    ax[0].axhline(tau_all.nominal_value,0,1,c='r',ls='-.',label=rf'$<\tau>$ = {tau_all:.1uf} ns')
    ax[0].axhspan(tau_all.nominal_value-tau_all.std_dev,tau_all.nominal_value+tau_all.std_dev, xmin=0, xmax=1,color='tab:red',alpha=0.4)
    ax[0].set_ylabel(r'$\tau$ (ns)')
    ax[0].set_title(f'\n{nombre.strip("*")} - {frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m')
    ax[1].plot(np.arange(len(SAR)), SAR,'o-', label=f'C = {concentracion/1000:.2f} g/L')
    ax[1].axhline(SAR_all.nominal_value,0,1,c='g',ls='-.',label=f'$<$SAR$>$ = {SAR_all:.1uf} W/g')
    ax[1].axhspan(SAR_all.nominal_value-SAR_all.std_dev,SAR_all.nominal_value+SAR_all.std_dev, xmin=0, xmax=1,color='tab:green',alpha=0.4)
    
    ax[1].set_xlabel('indx')
    ax[1].set_ylabel('SAR (W/g)')
    for a in ax:
        a.legend(ncol=2)
        a.grid()
    plt.suptitle(r'$\tau$ - SAR',fontsize=15)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_tau_SAR_vs_indx.png'),dpi=300,facecolor='w')
    plt.show()
    
    # Hc, Mr, Xi
    fig2, ax = plt.subplots(4, 1, figsize=(9,8), constrained_layout=True,sharex=True)
    ax[0].plot(np.arange(len(Coercitividad_kAm)),Coercitividad_kAm,'o-',label=f'H$_C$ = {Coercitividad_all:.1f} kA/m')
    ax[0].set_ylabel('Campo Coercitivo (kA/m)')
    ax[0].set_title(f'\n{nombre.strip("*")} - {frec_nombre[0]/1000:>3.0f} kHz - {round(np.mean(Campo_maximo)/1e3):>4.1f} kA/m')
    ax[1].plot(np.arange(len(xi_M_0)), xi_M_0,'s-',label='$\chi_{M=0}$ = '+f'{xi_all:.2e}')
    ax[1].set_ylabel('Suscept. a M=0')
    ax[2].plot(np.arange(len(Remanencia_Am)), Remanencia_Am,'D-',label='M$_R$ = '+f'{Remanencia_all:.0f} A/m')
    ax[2].set_ylabel('Mag Remanente')
    ax[3].plot(np.arange(len(Mag_max)), Mag_max,'v-',label='M$_{max}$ = '+f'{Mag_max_all:.0f} A/m')
    ax[3].set_ylabel('Mag Máxima')
    ax[3].set_xlabel('indx')
       
    
    for a in ax:
        a.legend(ncol=2)
        a.grid()
    plt.suptitle(r'H$_C$ - M$_R$ - $\chi_{M=0}$ - M$_{max}$',fontsize=15)
    plt.savefig(os.path.join(output_dir,os.path.commonprefix(list(fnames_m))+'_Hc_Mr_xi_vs_indx.png'),dpi=300,facecolor='w')
    
#%% Printeo Resultados del analisis
print('='*50)
print(f'Resultados analisis {fecha_graf}\n')
print(f'Concentracion {concentracion/1000} g/L\n')

print(f'''tau = {tau_all:.1f} ns
SAR = {SAR_all:.0f} W/g
dphi = {defasaje_all} rad

Campo Coercitivo = {Coercitividad_all:.2f} kA/m
Mag Remanente = {Remanencia_all:.0f} A/m
Mag maxima = {Mag_max_emu:.2f} emu/g
Susceptibilidad a M=0 = {xi_all:.e}''')
print('='*50)

#%%%
end_time = time.time()
print(f'Tiempo de ejecución del script: {(end_time-start_time):6.3f} s.')



# %%

# %%
