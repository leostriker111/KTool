; Instalador de ktool (Inno Setup). Toma el ejecutable que genera PyInstaller
; (dist\ktool.exe), lo instala por usuario (sin pedir administrador) y agrega
; su carpeta al PATH del usuario, para que `ktool` funcione desde cualquier carpeta.
; `kmap` queda como alias historico: un .cmd de una linea que llama a ktool.exe.

#define MyAppName "ktool"
#define MyAppVersion "0.5.0"
#define MyAppPublisher "Leostriker"
#define MyAppURL "https://github.com/leostriker111/ktool"

[Setup]
AppId={{B7D4F2A1-9C3E-4E6A-8F21-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\ktool
DefaultGroupName=ktool
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=ktool-setup
Compression=lzma
SolidCompression=yes
; Avisa a Windows que el PATH cambio, al instalar y al desinstalar. Sin esto,
; ni las terminales nuevas abiertas desde el Explorador ven la carpeta.
ChangesEnvironment=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
spanish.FinishedLabel=Listo: ktool quedo instalado y su carpeta se agrego al PATH de tu usuario.%n%nAbre una terminal NUEVA (las que ya estaban abiertas no ven el cambio) y escribe:%n%n    ktool -h%n    ktool gui%n%nFunciona desde cualquier carpeta. El comando kmap sigue funcionando como alias.

[InstallDelete]
; Hasta la 0.4.0 el ejecutable se llamaba kmap.exe. Si se queda, Windows lo
; prefiere sobre kmap.cmd y el alias apuntaria a la version vieja.
Type: files; Name: "{app}\kmap.exe"

[Files]
Source: "..\dist\ktool.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "alias-kmap.cmd"; DestDir: "{app}"; DestName: "kmap.cmd"; Flags: ignoreversion

[Icons]
Name: "{group}\ktool (interfaz grafica)"; Filename: "{app}\ktool.exe"; Parameters: "gui"
Name: "{group}\Desinstalar ktool"; Filename: "{uninstallexe}"

[Code]
// El PATH del usuario vive en HKCU\Environment, valor "Path". Se edita a mano
// (y no con una entrada de [Registry]) por dos razones: para poder quitarlo al
// desinstalar, y para no duplicar la carpeta si alguien reinstala.

// Saca el primer pedazo de una lista separada por ';' y deja el resto en Resto.
function SacarPrimero(var Resto: string): string;
var
  P: Integer;
begin
  P := Pos(';', Resto);
  if P = 0 then
  begin
    Result := Resto;
    Resto := '';
  end
  else
  begin
    Result := Copy(Resto, 1, P - 1);
    Resto := Copy(Resto, P + 1, Length(Resto));
  end;
end;

// Dos rutas son la misma carpeta aunque difieran en mayusculas o en la '\' final.
function MismaCarpeta(A, B: string): Boolean;
begin
  Result := Lowercase(RemoveBackslash(Trim(A))) = Lowercase(RemoveBackslash(Trim(B)));
end;

// Devuelve la lista sin la carpeta de ktool (y sin pedazos vacios, los ';;').
function QuitarCarpeta(Lista, Carpeta: string): string;
var
  Resto, Pedazo: string;
begin
  Result := '';
  Resto := Lista;
  while Resto <> '' do
  begin
    Pedazo := SacarPrimero(Resto);
    if (Trim(Pedazo) <> '') and (not MismaCarpeta(Pedazo, Carpeta)) then
    begin
      if Result = '' then
        Result := Pedazo
      else
        Result := Result + ';' + Pedazo;
    end;
  end;
end;

// Lee el PATH del usuario tal cual esta guardado (las %variables% sin expandir).
// Devuelve False solo si el valor existe pero no se pudo leer: en ese caso no
// hay que escribir nada, o se borraria el PATH que la persona ya tenia.
function LeerPathUsuario(var Valor: string): Boolean;
begin
  Valor := '';
  if not RegValueExists(HKEY_CURRENT_USER, 'Environment', 'Path') then
  begin
    Result := True;
    exit;
  end;
  Result := RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Valor);
end;

// Pone la carpeta al final del PATH una sola vez: primero la quita si ya
// estaba (reinstalacion) y luego la agrega.
procedure AgregarAlPath(Carpeta: string);
var
  Actual, Nuevo: string;
begin
  if not LeerPathUsuario(Actual) then
  begin
    MsgBox('No se pudo leer tu PATH, asi que no se modifico.' + #13#10 +
      'Agrega a mano esta carpeta: ' + Carpeta, mbError, MB_OK);
    exit;
  end;
  Nuevo := QuitarCarpeta(Actual, Carpeta);
  if Nuevo = '' then
    Nuevo := Carpeta
  else
    Nuevo := Nuevo + ';' + Carpeta;
  if not RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Nuevo) then
    MsgBox('No se pudo escribir tu PATH.' + #13#10 +
      'Agrega a mano esta carpeta: ' + Carpeta, mbError, MB_OK)
  else
    Log('PATH del usuario actualizado con ' + Carpeta);
end;

// Al desinstalar se deja el PATH como estaba antes de ktool.
procedure QuitarDelPath(Carpeta: string);
var
  Actual: string;
begin
  if not LeerPathUsuario(Actual) then
    exit;
  RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path',
    QuitarCarpeta(Actual, Carpeta));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AgregarAlPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    QuitarDelPath(ExpandConstant('{app}'));
end;
