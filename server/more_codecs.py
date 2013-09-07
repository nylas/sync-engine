#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
From here: https://github.com/nandoflorestan/bag/blob/master/bag/more_codecs.py

What do you do when Python does not know about some exotic encoder or
decoder that exists out there? Suppose you have some text,
perhaps an e-mail message, that Python won't decode, saying:

    LookupError: unknown encoding: ansi_x3.110-1983

What you do is tell Python to call some UNIX command that does the
encoding/decoding for you. This module sets that up using the iconv program.

Usage:

    import bag.more_codecs

That is it. Importing the module registers a codec. It will convert
to and from anything in codecs_dict (if iconv supports it).

However, the only possible error modes are 'strict' and 'ignore'. Therefore,
this raises an exception:

    u'hi'.encode('utf32', errors='replace')

The module will look for iconv in the path. You may set a specific location:

    bag.more_codecs.COMMAND = '/usr/bin/iconv'

Unfortunately performance suffers:
A process is started for every iconv call.
You can help us by writing code that calls iconv by using ctypes
or something like that.

Both Python and iconv change over time, so the list of codecs that each
supports is prolly going to change. The registered codecs are in a dictionary:

    from oui.more_codecs import codecs_dict
    print(list(codecs_dict.keys()))

You may add and remove codecs from the codecs_dict.

A reasonable, but perhaps not bug-free, method has been used to try to
determine which codecs iconv has that Python 2.5 does not, and this has
resulted in the default value of codecs_dict, with 894 codecs.
"""

import codecs
import subprocess
import os

COMMAND = 'iconv'
codecs_dict = [
    '500v1', '851', '856', '866nav', '874', '904', '1046', '1047', '8859_1',
    '8859_2', '8859_3', '8859_4', '8859_5', '8859_6', '8859_7', '8859_8',
    '8859_9', '10646-1:1993', '10646-1:1993/ucs4', 'ansi_x3.4',
    'ansi_x3.110-1983', 'ansi_x3.110', 'arabic7', 'armscii-8', 'asmo_449',
    'baltic', 'big-5', 'big-five', 'bigfive', 'brf', 'bs_4730', 'ca',
    'cn-big5', 'cn-gb', 'cn', 'cp-ar', 'cp-hu', 'cp038', 'cp273', 'cp274',
    'cp275', 'cp278', 'cp280', 'cp281', 'cp282', 'cp284', 'cp285', 'cp290',
    'cp297', 'cp420', 'cp423', 'cp803', 'cp813', 'cp851', 'cp866nav',
    'cp868', 'cp870', 'cp871', 'cp880', 'cp891', 'cp901', 'cp902', 'cp903',
    'cp904', 'cp905', 'cp912', 'cp915', 'cp916', 'cp918', 'cp920', 'cp921',
    'cp922', 'cp930', 'cp933', 'cp935', 'cp937', 'cp939', 'cp1004', 'cp1008',
    'cp1025', 'cp1046', 'cp1047', 'cp1070', 'cp1079', 'cp1081', 'cp1084',
    'cp1089', 'cp1097', 'cp1112', 'cp1122', 'cp1123', 'cp1124', 'cp1125',
    'cp1129', 'cp1130', 'cp1132', 'cp1133', 'cp1137', 'cp1141', 'cp1142',
    'cp1143', 'cp1144', 'cp1145', 'cp1146', 'cp1147', 'cp1148', 'cp1149',
    'cp1153', 'cp1154', 'cp1155', 'cp1156', 'cp1157', 'cp1158', 'cp1160',
    'cp1161', 'cp1162', 'cp1163', 'cp1164', 'cp1166', 'cp1167', 'cp1282',
    'cp1364', 'cp1371', 'cp1388', 'cp1390', 'cp1399', 'cp4517', 'cp4899',
    'cp4909', 'cp4971', 'cp5347', 'cp9030', 'cp9066', 'cp9448', 'cp10007',
    'cp12712', 'cp16804', 'cpibm861', 'csa7-1', 'csa7-2', 'csa_t500-1983',
    'csa_t500', 'csa_z243.4-1985-1', 'csa_z243.4-1985-2', 'csa_z243.419851',
    'csa_z243.419852', 'csdecmcs', 'csebcdicatde', 'csebcdicatdea',
    'csebcdiccafr', 'csebcdicdkno', 'csebcdicdknoa', 'csebcdices',
    'csebcdicesa', 'csebcdicess', 'csebcdicfise', 'csebcdicfisea',
    'csebcdicfr', 'csebcdicit', 'csebcdicpt', 'csebcdicuk', 'csebcdicus',
    'cseuckr', 'cseucpkdfmtjapanese', 'csgb2312', 'cshproman8', 'csibm038',
    'csibm273', 'csibm274', 'csibm275', 'csibm277', 'csibm278', 'csibm280',
    'csibm281', 'csibm284', 'csibm285', 'csibm290', 'csibm297', 'csibm420',
    'csibm423', 'csibm803', 'csibm851', 'csibm856', 'csibm868', 'csibm870',
    'csibm871', 'csibm880', 'csibm891', 'csibm901', 'csibm902', 'csibm903',
    'csibm904', 'csibm905', 'csibm918', 'csibm921', 'csibm922', 'csibm930',
    'csibm932', 'csibm933', 'csibm935', 'csibm937', 'csibm939', 'csibm943',
    'csibm1008', 'csibm1025', 'csibm1097', 'csibm1112', 'csibm1122',
    'csibm1123', 'csibm1124', 'csibm1129', 'csibm1130', 'csibm1132',
    'csibm1133', 'csibm1137', 'csibm1140', 'csibm1141', 'csibm1142',
    'csibm1143', 'csibm1144', 'csibm1145', 'csibm1146', 'csibm1147',
    'csibm1148', 'csibm1149', 'csibm1153', 'csibm1154', 'csibm1155',
    'csibm1156', 'csibm1157', 'csibm1158', 'csibm1160', 'csibm1161',
    'csibm1163', 'csibm1164', 'csibm1166', 'csibm1167', 'csibm1364',
    'csibm1371', 'csibm1388', 'csibm1390', 'csibm1399', 'csibm4517',
    'csibm4899', 'csibm4909', 'csibm4971', 'csibm5347', 'csibm9030',
    'csibm9066', 'csibm9448', 'csibm12712', 'csibm16804', 'csibm11621162',
    'csiso4unitedkingdom', 'csiso10swedish', 'csiso11swedishfornames',
    'csiso14jisc6220ro', 'csiso15italian', 'csiso16portugese',
    'csiso17spanish', 'csiso18greek7old', 'csiso19latingreek',
    'csiso21german', 'csiso25french', 'csiso27latingreek1', 'csiso49inis',
    'csiso50inis8', 'csiso51iniscyrillic', 'csiso58gb1988',
    'csiso60danishnorwegian', 'csiso60norwegian1', 'csiso61norwegian2',
    'csiso69french', 'csiso84portuguese2', 'csiso85spanish2',
    'csiso86hungarian', 'csiso88greek7', 'csiso89asmo449', 'csiso90',
    'csiso92jisc62991984b', 'csiso99naplps', 'csiso103t618bit',
    'csiso111ecmacyrillic', 'csiso121canadian1', 'csiso122canadian2',
    'csiso139csn369103', 'csiso141jusib1002', 'csiso143iecp271', 'csiso150',
    'csiso150greekccitt', 'csiso151cuba', 'csiso153gost1976874',
    'csiso646danish', 'csiso2022cn', 'csiso2022jp2', 'csiso2033',
    'csiso5427cyrillic', 'csiso5427cyrillic1981', 'csiso5428greek',
    'csiso10367box', 'csksc5636', 'csmacintosh', 'csnatsdano', 'csnatssefi',
    'csn_369103', 'csucs4', 'csunicode', 'cswindows31j', 'cuba', 'cwi-2',
    'cwi', 'de', 'dec-mcs', 'dec', 'decmcs', 'din_66003', 'dk', 'ds2089',
    'ds_2089', 'e13b', 'ebcdic-at-de-a', 'ebcdic-at-de', 'ebcdic-be',
    'ebcdic-br', 'ebcdic-ca-fr', 'ebcdic-cp-ar1', 'ebcdic-cp-ar2',
    'ebcdic-cp-dk', 'ebcdic-cp-es', 'ebcdic-cp-fi', 'ebcdic-cp-fr',
    'ebcdic-cp-gb', 'ebcdic-cp-gr', 'ebcdic-cp-is', 'ebcdic-cp-it',
    'ebcdic-cp-no', 'ebcdic-cp-roece', 'ebcdic-cp-se', 'ebcdic-cp-tr',
    'ebcdic-cp-yu', 'ebcdic-cyrillic', 'ebcdic-dk-no-a', 'ebcdic-dk-no',
    'ebcdic-es-a', 'ebcdic-es-s', 'ebcdic-es', 'ebcdic-fi-se-a',
    'ebcdic-fi-se', 'ebcdic-fr', 'ebcdic-greek', 'ebcdic-int', 'ebcdic-int1',
    'ebcdic-is-friss', 'ebcdic-it', 'ebcdic-jp-e', 'ebcdic-jp-kana',
    'ebcdic-pt', 'ebcdic-uk', 'ebcdic-us', 'ebcdicatde', 'ebcdicatdea',
    'ebcdiccafr', 'ebcdicdkno', 'ebcdicdknoa', 'ebcdices', 'ebcdicesa',
    'ebcdicess', 'ebcdicfise', 'ebcdicfisea', 'ebcdicfr', 'ebcdicisfriss',
    'ebcdicit', 'ebcdicpt', 'ebcdicuk', 'ebcdicus', 'ecma-128',
    'ecma-cyrillic', 'ecmacyrillic', 'es', 'es2', 'euc-jp-ms', 'euc-tw',
    'eucjp-ms', 'eucjp-open', 'eucjp-win', 'euctw', 'fi', 'fr', 'gb',
    'gb13000', 'gb_1988-80', 'gb_198880', 'georgian-academy', 'georgian-ps',
    'gost_19768-74', 'gost_19768', 'gost_1976874', 'greek-ccitt',
    'greek7-old', 'greek7', 'greek7old', 'greekccitt', 'hp-greek8',
    'hp-roman9', 'hp-thai8', 'hp-turkish8', 'hpgreek8', 'hproman8',
    'hproman9', 'hpthai8', 'hpturkish8', 'hu', 'ibm-803', 'ibm-856',
    'ibm-901', 'ibm-902', 'ibm-921', 'ibm-922', 'ibm-930', 'ibm-932',
    'ibm-933', 'ibm-935', 'ibm-937', 'ibm-939', 'ibm-943', 'ibm-1008',
    'ibm-1025', 'ibm-1046', 'ibm-1047', 'ibm-1097', 'ibm-1112', 'ibm-1122',
    'ibm-1123', 'ibm-1124', 'ibm-1129', 'ibm-1130', 'ibm-1132', 'ibm-1133',
    'ibm-1137', 'ibm-1140', 'ibm-1141', 'ibm-1142', 'ibm-1143', 'ibm-1144',
    'ibm-1145', 'ibm-1146', 'ibm-1147', 'ibm-1148', 'ibm-1149', 'ibm-1153',
    'ibm-1154', 'ibm-1155', 'ibm-1156', 'ibm-1157', 'ibm-1158', 'ibm-1160',
    'ibm-1161', 'ibm-1162', 'ibm-1163', 'ibm-1164', 'ibm-1166', 'ibm-1167',
    'ibm-1364', 'ibm-1371', 'ibm-1388', 'ibm-1390', 'ibm-1399', 'ibm-4517',
    'ibm-4899', 'ibm-4909', 'ibm-4971', 'ibm-5347', 'ibm-9030', 'ibm-9066',
    'ibm-9448', 'ibm-12712', 'ibm-16804', 'ibm038', 'ibm256', 'ibm273',
    'ibm274', 'ibm275', 'ibm277', 'ibm278', 'ibm280', 'ibm281', 'ibm284',
    'ibm285', 'ibm290', 'ibm297', 'ibm420', 'ibm423', 'ibm803', 'ibm813',
    'ibm848', 'ibm851', 'ibm856', 'ibm866nav', 'ibm868', 'ibm870', 'ibm871',
    'ibm874', 'ibm875', 'ibm880', 'ibm891', 'ibm901', 'ibm902', 'ibm903',
    'ibm904', 'ibm905', 'ibm912', 'ibm915', 'ibm916', 'ibm918', 'ibm920',
    'ibm921', 'ibm922', 'ibm930', 'ibm932', 'ibm933', 'ibm935', 'ibm937',
    'ibm939', 'ibm943', 'ibm1004', 'ibm1008', 'ibm1025', 'ibm1046', 'ibm1047',
    'ibm1089', 'ibm1097', 'ibm1112', 'ibm1122', 'ibm1123', 'ibm1124',
    'ibm1129', 'ibm1130', 'ibm1132', 'ibm1133', 'ibm1137', 'ibm1141',
    'ibm1142', 'ibm1143', 'ibm1144', 'ibm1145', 'ibm1146', 'ibm1147',
    'ibm1148', 'ibm1149', 'ibm1153', 'ibm1154', 'ibm1155', 'ibm1156',
    'ibm1157', 'ibm1158', 'ibm1160', 'ibm1161', 'ibm1162', 'ibm1163',
    'ibm1164', 'ibm1166', 'ibm1167', 'ibm1364', 'ibm1371', 'ibm1388',
    'ibm1390', 'ibm1399', 'ibm4517', 'ibm4899', 'ibm4909', 'ibm4971',
    'ibm5347', 'ibm9030', 'ibm9066', 'ibm9448', 'ibm12712', 'ibm16804',
    'iec_p27-1', 'iec_p271', 'inis-8', 'inis-cyrillic', 'inis', 'inis8',
    'iniscyrillic', 'isiri-3342', 'isiri3342', 'iso-2022-cn-ext',
    'iso-2022-cn', 'iso-8859-9e', 'iso-10646', 'iso-10646/ucs2',
    'iso-10646/ucs4', 'iso-10646/utf-8', 'iso-10646/utf8', 'iso-ir-4',
    'iso-ir-8-1', 'iso-ir-9-1', 'iso-ir-10', 'iso-ir-11', 'iso-ir-14',
    'iso-ir-15', 'iso-ir-16', 'iso-ir-17', 'iso-ir-18', 'iso-ir-19',
    'iso-ir-21', 'iso-ir-25', 'iso-ir-27', 'iso-ir-37', 'iso-ir-49',
    'iso-ir-50', 'iso-ir-51', 'iso-ir-54', 'iso-ir-55', 'iso-ir-57',
    'iso-ir-60', 'iso-ir-61', 'iso-ir-69', 'iso-ir-84', 'iso-ir-85',
    'iso-ir-86', 'iso-ir-88', 'iso-ir-89', 'iso-ir-90', 'iso-ir-92',
    'iso-ir-98', 'iso-ir-99', 'iso-ir-103', 'iso-ir-111', 'iso-ir-121',
    'iso-ir-122', 'iso-ir-139', 'iso-ir-141', 'iso-ir-143', 'iso-ir-150',
    'iso-ir-151', 'iso-ir-153', 'iso-ir-155', 'iso-ir-156', 'iso-ir-179',
    'iso-ir-193', 'iso-ir-197', 'iso-ir-203', 'iso-ir-209', 'iso/tr_11548-1',
    'iso646-ca', 'iso646-ca2', 'iso646-cn', 'iso646-cu', 'iso646-de',
    'iso646-dk', 'iso646-es', 'iso646-es2', 'iso646-fi', 'iso646-fr',
    'iso646-fr1', 'iso646-gb', 'iso646-hu', 'iso646-it', 'iso646-jp-ocr-b',
    'iso646-jp', 'iso646-kr', 'iso646-no', 'iso646-no2', 'iso646-pt',
    'iso646-pt2', 'iso646-se', 'iso646-se2', 'iso646-yu', 'iso2022cn',
    'iso2022cnext', 'iso2022jp2', 'iso6937', 'iso8859-9e', 'iso11548-1',
    'iso88591', 'iso88592', 'iso88593', 'iso88594', 'iso88595', 'iso88596',
    'iso88597', 'iso88598', 'iso88599', 'iso88599e', 'iso885910', 'iso885911',
    'iso885913', 'iso885914', 'iso885915', 'iso885916', 'iso_2033-1983',
    'iso_2033', 'iso_5427-ext', 'iso_5427', 'iso_5427:1981', 'iso_5427ext',
    'iso_5428', 'iso_5428:1980', 'iso_6937-2', 'iso_6937-2:1983', 'iso_6937',
    'iso_6937:1992', 'iso_8859-7:2003', 'iso_8859-9e', 'iso_8859-15:1998',
    'iso_9036', 'iso_10367-box', 'iso_10367box', 'iso_11548-1', 'iso_69372',
    'it', 'jis_c6220-1969-ro', 'jis_c6229-1984-b', 'jis_c62201969ro',
    'jis_c62291984b', 'jp-ocr-b', 'jp', 'js', 'jus_i.b1.002', 'koi-7',
    'koi-8', 'koi8-ru', 'koi8-t', 'koi8', 'koi8r', 'koi8u', 'ksc5636', 'l7',
    'latin-9', 'latin-greek-1', 'latin-greek', 'latin7', 'latingreek',
    'latingreek1', 'mac-centraleurope', 'mac-is', 'mac-sami', 'mac-uk', 'mac',
    'macintosh', 'macis', 'macuk', 'macukrainian', 'mik', 'ms-ansi',
    'ms-arab', 'ms-cyrl', 'ms-ee', 'ms-greek', 'ms-hebr', 'ms-mac-cyrillic',
    'ms-turk', 'mscp949', 'mscp1361', 'msmaccyrillic', 'msz_7795.3', 'naplps',
    'nats-dano', 'nats-sefi', 'natsdano', 'natssefi', 'nc_nc0010',
    'nc_nc00-10', 'nc_nc00-10:81', 'nf_z_62-010', 'nf_z_62-010_(1973)',
    'nf_z_62-010_1973', 'nf_z_62010', 'nf_z_62010_1973', 'no', 'no2',
    'ns_4551-1', 'ns_4551-2', 'ns_45511', 'ns_45512', 'os2latin1',
    'osf00010001', 'osf00010002', 'osf00010003', 'osf00010004', 'osf00010005',
    'osf00010006', 'osf00010007', 'osf00010008', 'osf00010009', 'osf0001000a',
    'osf00010020', 'osf00010100', 'osf00010101', 'osf00010102', 'osf00010104',
    'osf00010105', 'osf00010106', 'osf00030010', 'osf0004000a', 'osf0005000a',
    'osf05010001', 'osf100201a4', 'osf100201a8', 'osf100201b5', 'osf100201f4',
    'osf100203b5', 'osf1002011c', 'osf1002011d', 'osf1002035d', 'osf1002035e',
    'osf1002035f', 'osf1002036b', 'osf1002037b', 'osf10010001', 'osf10010004',
    'osf10010006', 'osf10020025', 'osf10020111', 'osf10020115', 'osf10020116',
    'osf10020118', 'osf10020122', 'osf10020129', 'osf10020352', 'osf10020354',
    'osf10020357', 'osf10020359', 'osf10020360', 'osf10020364', 'osf10020365',
    'osf10020366', 'osf10020367', 'osf10020370', 'osf10020387', 'osf10020388',
    'osf10020396', 'osf10020402', 'osf10020417', 'pt', 'pt2', 'r9', 'rk1048',
    'roman9', 'ruscii', 'se', 'se2', 'sen_850200_b', 'sen_850200_c',
    'sjis-open', 'sjis-win', 'ss636127', 'strk1048-2002', 'st_sev_358-88',
    't.61-8bit', 't.61', 't.618bit', 'tcvn-5712', 'tcvn', 'tcvn5712-1',
    'tcvn5712-1:1993', 'thai8', 'tis620-0', 'tis620.2529-1', 'tis620.2533-0',
    'ts-5881', 'tscii', 'turkish8', 'ucs-2', 'ucs-2be', 'ucs-2le', 'ucs-4',
    'ucs-4be', 'ucs-4le', 'ucs2', 'ucs4', 'uk', 'unicode', 'unicodebig',
    'unicodelittle', 'utf-32', 'utf-32be', 'utf-32le', 'utf16be', 'utf16le',
    'utf32', 'utf32be', 'utf32le', 'viscii', 'wchar_t', 'win-sami-2',
    'winbaltrim', 'windows-31j', 'windows-874', 'windows-936', 'winsami2',
    'ws2', 'yu']

codecs_dict = dict(zip(codecs_dict, codecs_dict))


def get_supported_codecs():
    """Returns a list of the codec names that iconv supports."""
    cmd = [COMMAND, '--list']
    iconv = subprocess.Popen(cmd, env={'LANG': 'C'},
                             stdout=subprocess.PIPE,
                             stdin=open(os.devnull, 'w+'),
                             stderr=open(os.devnull, 'w+'))
    return [line.strip('/').lower() for line in
            iconv.communicate()[0].splitlines()]


def discover_interesting_codecs():
    global codecs_dict
    temp = codecs_dict
    codecs_dict = {}  # deactivate iconv for now
    supported_codecs = get_supported_codecs()
    interesting_codecs = []
    for c in supported_codecs:
        try:
            u'a'.encode(c)
        except UnicodeEncodeError:
            pass
        except LookupError:
            interesting_codecs.append(c)
    codecs_dict = temp  # reactivate iconv
    return interesting_codecs


''' From Python documentation:
#Codec  Aliases
_python_codecs = """
ascii   646, us-ascii
big5    big5-tw, csbig5
big5hkscs   big5-hkscs, hkscs
cp037   IBM037, IBM039
cp424   EBCDIC-CP-HE, IBM424
cp437   437, IBM437
cp500   EBCDIC-CP-BE, EBCDIC-CP-CH, IBM500
cp737
cp775   IBM775
cp850   850, IBM850
cp852   852, IBM852
cp855   855, IBM855
cp856
cp857   857, IBM857
cp860   860, IBM860
cp861   861, CP-IS, IBM861
cp862   862, IBM862
cp863   863, IBM863
cp864   IBM864
cp865   865, IBM865
cp866   866, IBM866
cp869   869, CP-GR, IBM869
cp874
cp875
cp932   932, ms932, mskanji, ms-kanji
cp949   949, ms949, uhc
cp950   950, ms950
cp1006
cp1026  ibm1026
cp1140  ibm1140
cp1250  windows-1250
cp1251  windows-1251
cp1252  windows-1252
cp1253  windows-1253
cp1254  windows-1254
cp1255  windows-1255
cp1256  windows1256
cp1257  windows-1257
cp1258  windows-1258
euc_jp  eucjp, ujis, u-jis
euc_jis_2004    jisx0213, eucjis2004
euc_jisx0213    eucjisx0213
euc_kr  euckr, korean, ksc5601, ks_c-5601, ks_c-5601-1987, ksx1001, ks_x-1001
gb2312  chinese, csiso58gb231280, euc- cn, euccn, eucgb2312-cn, gb2312-1980, gb2312-80, iso- ir-58
gbk 936, cp936, ms936
gb18030 gb18030-2000
hz  hzgb, hz-gb, hz-gb-2312
iso2022_jp  csiso2022jp, iso2022jp, iso-2022-jp
iso2022_jp_1    iso2022jp-1, iso-2022-jp-1
iso2022_jp_2    iso2022jp-2, iso-2022-jp-2
iso2022_jp_2004 iso2022jp-2004, iso-2022-jp-2004
iso2022_jp_3    iso2022jp-3, iso-2022-jp-3
iso2022_jp_ext  iso2022jp-ext, iso-2022-jp-ext
iso2022_kr  csiso2022kr, iso2022kr, iso-2022-kr
latin_1 iso-8859-1, iso8859-1, 8859, cp819, latin, latin1, L1
iso8859_2   iso-8859-2, latin2, L2
iso8859_3   iso-8859-3, latin3, L3
iso8859_4   iso-8859-4, latin4, L4
iso8859_5   iso-8859-5, cyrillic
iso8859_6   iso-8859-6, arabic
iso8859_7   iso-8859-7, greek, greek8
iso8859_8   iso-8859-8, hebrew
iso8859_9   iso-8859-9, latin5, L5
iso8859_10  iso-8859-10, latin6, L6
iso8859_13  iso-8859-13
iso8859_14  iso-8859-14, latin8, L8
iso8859_15  iso-8859-15
johab   cp1361, ms1361
koi8_r
koi8_u
mac_cyrillic    maccyrillic
mac_greek   macgreek
mac_iceland maciceland
mac_latin2  maclatin2, maccentraleurope
mac_roman   macroman
mac_turkish macturkish
ptcp154 csptcp154, pt154, cp154, cyrillic-asian
shift_jis   csshiftjis, shiftjis, sjis, s_jis
shift_jis_2004  shiftjis2004, sjis_2004, sjis2004
shift_jisx0213  shiftjisx0213, sjisx0213, s_jisx0213
utf_32  U32, utf32
utf_32_be   UTF-32BE
utf_32_le   UTF-32LE
utf_16  U16, utf16
utf_16_be   UTF-16BE
utf_16_le   UTF-16LE
utf_7   U7, unicode-1-1-utf-7
utf_8   U8, UTF, utf8
utf_8_sig
"""
_python_codecs = re.findall(r"([^\r\n\t ,]+)", python_codecs.lower())
additional_codecs = [c for c in supported_codecs \
                     if c != 'utf-8' and c not in python_codecs]
'''


def _run_iconv(from_codec, to_codec, extra_params=None):
    cmd = [COMMAND, '-f', from_codec, '-t', to_codec, '-s']  # -s is silent
    if extra_params:
        cmd.extend(extra_params)
    iconv = subprocess.Popen(cmd, env={'LANG': 'C'}, stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    return iconv


def _iconv_factory(codec_name):
    codec_name = codec_name.lower()
    if codec_name in codecs_dict:
        def iconvencode(input, errors='strict', encoding=codec_name):
            extra = []
            if errors == 'ignore':
                extra.append('-c')
            elif errors != 'strict':
                raise NotImplementedError("%r error handling not implemented"
                                          " for codec %r" % (errors, encoding))
            _input = input.encode('utf-8')
            iconv = _run_iconv('utf-8', encoding, extra)
            output, error = iconv.communicate(_input)
            if error:
                error = error.splitlines()[0]
                raise UnicodeEncodeError(encoding, input, 0, len(input), error)
            return output, len(input)

        def iconvdecode(input, errors='strict', encoding=codec_name):
            extra = []
            if errors == 'ignore':
                extra.append('-c')
            elif errors != 'strict':
                raise NotImplementedError('%r error handling not implemented'
                                          ' for codec %r' % (errors, encoding))
            _input = str(input)
            iconv = _run_iconv(encoding, 'utf-8', extra)
            output, error = iconv.communicate(_input)
            if error:
                error = error.splitlines()[0]
                raise UnicodeDecodeError(encoding, input, 0, len(input), error)
            output = output.decode('utf-8')
            return output, len(input)

        class IncrementalEncoder(codecs.IncrementalEncoder):
            def encode(self, input, final=False):
                return iconvencode(input, self.errors)[0]

        class IncrementalDecoder(codecs.BufferedIncrementalDecoder):
            _buffer_decode = staticmethod(iconvdecode)

        class StreamWriter(codecs.StreamWriter):
            pass
        StreamWriter.encode = staticmethod(iconvencode)

        class StreamReader(codecs.StreamReader):
            pass
        StreamReader.decode = staticmethod(iconvdecode)

        return codecs.CodecInfo(
            name=codec_name,
            encode=iconvencode,
            decode=iconvdecode,
            incrementalencoder=IncrementalEncoder,
            incrementaldecoder=IncrementalDecoder,
            streamreader=StreamReader,
            streamwriter=StreamWriter,
        )


if __name__ == '__main__':
    interesting_codecs = discover_interesting_codecs()
    print("Here are the %i codecs that Python does not know, but iconv does:"
        % len(interesting_codecs))
    print(interesting_codecs)
    # Now register the codecs and test
    codecs.register(_iconv_factory)
    x = u'Ã¡Ã©Ã­Ã³ÃºÃ§Ã§Ã§'
    assert x == x.encode('utf32').decode('utf32')
else:
    codecs.register(_iconv_factory)