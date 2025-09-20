{
  lib,
  buildPythonPackage,
  requests
}:

buildPythonPackage rec {
  pname = "piqtec";
  version = "99.99.99";
  pyproject = true;

  disabled = pythonOlder "3.10";

  src = "./.";

  dependencies = [
    requests
  ];


  meta = with lib; {
    description = "IQtec smart-home Python inteface";
    homepage = "https://github.com/oberth-effect/piqtec";
    license = lib.licenses.cc-by-nc-sa-40;
    maintainers = with maintainers; [ oberth-effect ];
  };
}