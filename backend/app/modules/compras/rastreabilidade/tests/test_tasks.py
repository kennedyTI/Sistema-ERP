from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.celery_app import celery_app
from backend.app.modules.compras.rastreabilidade.importer import (
    ImportacaoRastreabilidadeResultado,
)
from backend.app.modules.compras.rastreabilidade.models import (
    ComprasRastreabilidadeExecucao,
    ComprasRastreabilidadeItem,
)
from backend.app.modules.compras.rastreabilidade.schemas import RastreabilidadeContagens
from backend.app.modules.compras.rastreabilidade.tasks import (
    compras_rastreabilidade_importar,
)
from backend.app.modules.compras.rastreabilidade.workflow import (
    IMPORT_LOCK_KEY,
    IMPORT_LOCK_TTL_SECONDS,
    executar_importacao_com_lock,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.ttls[key] = ex
        return True

    def eval(self, _script, _key_count, key, token):
        if self.values.get(key) != token:
            return 0
        del self.values[key]
        self.ttls.pop(key, None)
        return 1


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ComprasRastreabilidadeExecucao.__table__.create(engine)
    ComprasRastreabilidadeItem.__table__.create(engine)
    return sessionmaker(bind=engine)()


class ComprasRastreabilidadeTaskTest(TestCase):
    def test_task_registrada_e_agendada_em_cron_fixo(self):
        schedule = celery_app.conf.beat_schedule["compras-rastreabilidade-00-06-12-18"]

        self.assertIn("compras_rastreabilidade_importar", celery_app.tasks)
        self.assertEqual(compras_rastreabilidade_importar.name, "compras_rastreabilidade_importar")
        self.assertEqual(schedule["task"], "compras_rastreabilidade_importar")
        self.assertEqual(schedule["schedule"].minute, {0})
        self.assertEqual(schedule["schedule"].hour, {0, 6, 12, 18})
        self.assertEqual(schedule["kwargs"], {"origem": "agendada"})

    @patch("backend.app.modules.compras.rastreabilidade.tasks.get_redis_client")
    @patch("backend.app.modules.compras.rastreabilidade.tasks.SessionLocal")
    @patch("backend.app.modules.compras.rastreabilidade.tasks.executar_importacao_com_lock")
    def test_task_chama_fluxo_com_lock(self, run_with_lock, session_local, get_redis):
        db = make_session()
        redis = FakeRedis()
        session_local.return_value = db
        get_redis.return_value = redis
        run_with_lock.return_value = ImportacaoRastreabilidadeResultado(
            execucao_id=10,
            total_registros=5,
            contagens=RastreabilidadeContagens(),
        )

        result = compras_rastreabilidade_importar.run(origem="agendada")

        self.assertTrue(result["executada"])
        self.assertEqual(result["execucao_id"], 10)
        run_with_lock.assert_called_once()
        self.assertTrue(db.is_active)

    @patch("backend.app.modules.compras.rastreabilidade.tasks.get_redis_client")
    @patch("backend.app.modules.compras.rastreabilidade.tasks.SessionLocal")
    def test_task_respeita_lock_ativo(self, session_local, get_redis):
        db = make_session()
        redis = FakeRedis()
        redis.set(IMPORT_LOCK_KEY, "ativo")
        session_local.return_value = db
        get_redis.return_value = redis

        result = compras_rastreabilidade_importar.run(origem="agendada")

        self.assertFalse(result["executada"])
        self.assertEqual(result["motivo"], "importacao_em_andamento")


class ComprasRastreabilidadeWorkflowLockTest(TestCase):
    def test_lock_tem_ttl_e_e_liberado_em_sucesso(self):
        db = make_session()
        redis = FakeRedis()
        importer = Mock(
            return_value=ImportacaoRastreabilidadeResultado(
                execucao_id=1,
                total_registros=1,
                contagens=RastreabilidadeContagens(),
            )
        )

        with patch(
            "backend.app.modules.compras.rastreabilidade.workflow.importar_rastreabilidade_compras",
            importer,
        ):
            executar_importacao_com_lock(
                db,
                origem="agendada",
                redis_client=redis,
            )

        self.assertNotIn(IMPORT_LOCK_KEY, redis.values)
        self.assertEqual(redis.ttls, {})
        self.assertEqual(importer.call_args.kwargs["origem"], "agendada")

    def test_lock_e_liberado_em_erro(self):
        db = make_session()
        redis = FakeRedis()

        with patch(
            "backend.app.modules.compras.rastreabilidade.workflow.importar_rastreabilidade_compras",
            side_effect=RuntimeError("erro sanitizado pelo importador"),
        ):
            try:
                executar_importacao_com_lock(
                    db,
                    origem="agendada",
                    redis_client=redis,
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("Fluxo deveria propagar o erro.")

        self.assertNotIn(IMPORT_LOCK_KEY, redis.values)

    def test_ttl_do_lock_e_tres_horas(self):
        redis = FakeRedis()
        token = redis.set(IMPORT_LOCK_KEY, "token", nx=True, ex=IMPORT_LOCK_TTL_SECONDS)

        self.assertTrue(token)
        self.assertEqual(redis.ttls[IMPORT_LOCK_KEY], 10800)
