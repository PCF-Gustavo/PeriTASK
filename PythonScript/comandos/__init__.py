import importlib


def obter_funcao_comando(comando_id):
    """
    Carrega dinamicamente o módulo PythonScript/comandos/{comando_id}.py
    e retorna a função executar() desse módulo.
    """

    nome_modulo = f"comandos.{comando_id}"

    try:
        modulo = importlib.import_module(nome_modulo)
    except ModuleNotFoundError as exc:
        raise NotImplementedError(
            f"Comando '{comando_id}' ainda não implementado em comandos/{comando_id}.py"
        ) from exc

    funcao = getattr(modulo, "executar", None)

    if funcao is None:
        raise NotImplementedError(
            f"O arquivo comandos/{comando_id}.py precisa definir "
            f"a função executar(arquivos, ui_state, pasta_saida)"
        )

    if not callable(funcao):
        raise TypeError(
            f"'executar' em comandos/{comando_id}.py existe, mas não é uma função chamável"
        )

    return funcao


def executar_comando(comando_id, arquivos, ui_state, pasta_saida):
    """
    Executa dinamicamente um comando pelo ID recebido da UI.
    """

    funcao = obter_funcao_comando(comando_id)
    return funcao(arquivos, ui_state, pasta_saida)