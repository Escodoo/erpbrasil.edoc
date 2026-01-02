# coding=utf-8
# Copyright (C) 2020 KMEE

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import xml.etree.ElementTree as ET

from base64 import b64encode
from erpbrasil.edoc.nfse import NFSe
from erpbrasil.edoc.nfse import ServicoNFSe

try:
    from erpbrasil.assinatura.assinatura import Assinatura
    from nfselib.paulistana.v03 import PedidoCancelamentoNFe_v02
    from nfselib.paulistana.v03 import PedidoConsultaLote_v02
    from nfselib.paulistana.v03 import PedidoConsultaNFe_v02
    from nfselib.paulistana.v03 import RetornoCancelamentoNFe_v02
    from nfselib.paulistana.v03 import RetornoConsulta_v02
    from nfselib.paulistana.v03 import RetornoEnvioLoteRPS_v02
    paulistana = True
except ImportError:
    paulistana = False

endpoint = "lotenfe.asmx?WSDL"

if paulistana:
    servicos_base = {
        'consulta_recibo': ServicoNFSe(
            'ConsultaLote',
            endpoint, RetornoConsulta_v02, True),

        'consulta_nfse_rps': ServicoNFSe(
            'ConsultaNFe',
            endpoint, RetornoConsulta_v02, True),

        'cancela_documento': ServicoNFSe(
            'CancelamentoNFe',
            endpoint, RetornoCancelamentoNFe_v02, True),
    }

    servicos_hml = {
        'envia_documento': ServicoNFSe(
            'TesteEnvioLoteRPS',
            endpoint, RetornoEnvioLoteRPS_v02, True),
    }
    servicos_hml.update(servicos_base.copy())

    servicos_prod = {
        'envia_documento': ServicoNFSe(
            'EnvioLoteRPS',
            endpoint, RetornoEnvioLoteRPS_v02, True),
    }
    servicos_prod.update(servicos_base.copy())


class Paulistana(NFSe):

    def __init__(self, transmissao, ambiente, cidade_ibge, cnpj_prestador,
                 im_prestador):

        self._url = "https://nfews.prefeitura.sp.gov.br"

        # Não tem URL de homologação mas tem métodos para testes
        # no mesmo webservice

        if ambiente == '2':
            self._servicos = servicos_hml
        else:
            self._servicos = servicos_prod

        super(Paulistana, self).__init__(
            transmissao, ambiente, cidade_ibge, cnpj_prestador, im_prestador)

    def _prepara_envia_documento(self, edoc):
        assinador = Assinatura(self._transmissao.certificado)
        for rps in edoc.RPS:
            assinatura_bytes = assinador.sign_pkcs1v15_sha1(rps.Assinatura)
            rps.Assinatura = assinatura_bytes
        xml_assinado = self.assina_raiz(edoc, "")
        return xml_assinado

    def _verifica_resposta_envio_sucesso(self, proc_envio):
        return proc_envio.resposta.Cabecalho.Sucesso

    def _edoc_situacao_em_processamento(self, proc_recibo):
        # if proc_recibo.resposta.Situacao == 2:
        #     return True
        # return False
        pass

    def _prepara_consulta_recibo(self, proc_envio):

        retorno = ET.fromstring(proc_envio.retorno)
        numero_lote = int(retorno.find('.//NumeroLote').text)
        cnpj = retorno.find('.//CNPJ').text

        edoc = PedidoConsultaLote_v02.PedidoConsultaLote(
            Cabecalho=PedidoConsultaLote_v02.CabecalhoType(
                Versao=2,
                CPFCNPJRemetente=PedidoConsultaNFe_v02.tpCPFCNPJ(CNPJ=cnpj),
                NumeroLote=numero_lote
            )
        )

        xml_assinado = self.assina_raiz(edoc, '')

        return xml_assinado

    def _prepara_consultar_nfse_rps(self, **kwargs):
        cnpj_prestador = kwargs.get("cnpj_prest")
        inscricao_prestador = kwargs.get("insc_prest")
        rps_serie = kwargs.get("serie_rps")
        rps_numero = kwargs.get("numero_rps")

        raiz = PedidoConsultaNFe_v02.PedidoConsultaNFe(
            Cabecalho=PedidoConsultaNFe_v02.CabecalhoType(
                Versao=2,
                CPFCNPJRemetente=PedidoConsultaNFe_v02.tpCPFCNPJ(CNPJ=cnpj_prestador)
            ),
            Detalhe=[PedidoConsultaNFe_v02.DetalheType(
                ChaveRPS=PedidoConsultaNFe_v02.tpChaveRPS(
                    InscricaoPrestador=int(inscricao_prestador),
                    SerieRPS=rps_serie,
                    NumeroRPS=int(rps_numero),
                ),
            )],
        )

        xml_assinado = self.assina_raiz(raiz, '')

        return xml_assinado

    def analisa_retorno_consulta(self, processo):
        retorno_mensagem = ''
        res = {}
        if processo.resposta.Cabecalho.Sucesso:
            retorno = ET.fromstring(processo.retorno)
            res['codigo_verificacao'] = \
                retorno.find('.//CodigoVerificacao').text
            res['numero'] = retorno.find('.//NumeroNFe').text
            res['data_emissao'] = retorno.find('.//DataEmissaoNFe').text
            return res
        else:
            retorno_mensagem = 'Error communicating with the webservice'
            return retorno_mensagem

    def _prepara_cancelar_nfse_envio(self, doc_numero):
        numero_nfse = doc_numero.get('numero_nfse')
        codigo_verificacao = doc_numero.get('codigo_verificacao') or ''

        assinatura_raw = (
            self.im_prestador.zfill(12)
            + numero_nfse.zfill(12)
        )

        raiz = PedidoCancelamentoNFe_v02.PedidoCancelamentoNFe(
            Cabecalho=PedidoCancelamentoNFe_v02.CabecalhoType(
                Versao=2,
                CPFCNPJRemetente=PedidoConsultaNFe_v02.tpCPFCNPJ(CNPJ=self.cnpj_prestador),
            ),
            Detalhe=[PedidoCancelamentoNFe_v02.DetalheType(
                ChaveNFe=PedidoCancelamentoNFe_v02.tpChaveNFe(
                    InscricaoPrestador=int(self.im_prestador),
                    NumeroNFe=int(numero_nfse),
                    CodigoVerificacao=codigo_verificacao.zfill(8),
                ),
                AssinaturaCancelamento=None,
            )],
        )

        assinador = Assinatura(self._transmissao.certificado)
        for detalhe in raiz.Detalhe:
            assinatura_bytes = assinador.sign_pkcs1v15_sha1(
                assinatura_raw.encode('ascii')
            )
            detalhe.AssinaturaCancelamento = assinatura_bytes
        xml_assinado = self.assina_raiz(raiz, '')
        return xml_assinado

    def analisa_retorno_cancelamento_paulistana(self, processo):
        retorno_mensagem = ''
        status = True
        if not processo.resposta.Cabecalho.Sucesso:
            status = False
            for erro in processo.resposta.Erro:
                retorno_mensagem = \
                    str(erro.Codigo) + ' - ' + erro.Descricao + '\n'
        return status, retorno_mensagem

    def assina_raiz(self, raiz, id, getchildren=False):
        xml_string, xml_etree = self._generateds_to_string_etree(raiz)
        xml_assinado = Assinatura(self._transmissao.certificado).assina_nfse(
            xml_etree
        )
        return xml_assinado
