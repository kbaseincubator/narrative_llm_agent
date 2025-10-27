import pytest
from unittest.mock import Mock, patch, MagicMock, call
import argparse
import json
from typing import Any

from scripts.full_pipeline import (
    PipelineConfig,
    parse_args,
    data_type_to_params,
    import_data,
    import_data_file,
    copy_data_object,
    process_metadata,
    run_analysis_workflow,
    run_execution_workflow,
    write_draft_mra,
    run_pipeline,
    ASSEMBLY,
    PE_READS_INT,
    PE_READS_NON_INT,
    SE_READS,
    DATA_TYPES,
)


class TestPipelineConfig:
    """Test PipelineConfig pydantic model."""

    def test_pipeline_config_basic(self):
        """Test basic PipelineConfig creation."""
        config = PipelineConfig(
            kbase_token="test_token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test Narrative",
            input_data_type="assembly",
            input_upa="1/2/3"
        )
        assert config.kbase_token == "test_token"
        assert config.llm_provider == "cborg"
        assert config.llm_token == "llm_token"
        assert config.narrative_name == "Test Narrative"
        assert config.input_data_type == "assembly"
        assert config.input_upa == "1/2/3"
        assert config.input_file_path is None
        assert config.input_file_path2 is None
        assert config.input_data_params is None

    def test_pipeline_config_with_file_paths(self):
        """Test PipelineConfig with file paths."""
        params = {"app_id": "test_app", "params": {"key": "value"}}
        config = PipelineConfig(
            kbase_token="test_token",
            llm_provider="openai",
            llm_token="llm_token",
            narrative_name="Test Narrative",
            input_file_path="/path/to/file.fa",
            input_file_path2="/path/to/file2.fa",
            input_data_type="pe_reads_noninterleaved",
            input_data_params=params,
            input_upa=None
        )
        assert config.input_file_path == "/path/to/file.fa"
        assert config.input_file_path2 == "/path/to/file2.fa"
        assert config.input_data_params == params
        assert config.input_upa is None


class TestParseArgs:
    """Test parse_args function."""

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'cborg', '-l', 'llm_key',
                        '-f', '/staging/test.fa', '-t', 'assembly'])
    @patch('scripts.full_pipeline.Workspace')
    def test_parse_args_with_file(self, mock_ws):
        """Test parse_args with file input."""
        config = parse_args()

        assert config.kbase_token == "token123"
        assert config.llm_provider == "cborg"
        assert config.llm_token == "llm_key"
        assert config.input_file_path == "/staging/test.fa"
        assert config.input_data_type == "assembly"
        assert config.narrative_name == "LLM Agent Annotation for test.fa"
        assert config.input_upa is None
        assert config.input_data_params is not None
        assert config.input_data_params["app_id"] == "kb_uploadmethods/import_fasta_as_assembly_from_staging"

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'openai', '-l', 'llm_key',
                        '-u', '1/2/3', '-t', 'assembly'])
    @patch('scripts.full_pipeline.Workspace')
    def test_parse_args_with_upa(self, mock_ws):
        """Test parse_args with UPA input."""
        mock_ws_instance = mock_ws.return_value
        mock_obj_info = Mock()
        mock_obj_info.name = "test_object"
        mock_ws_instance.get_object_info.return_value = mock_obj_info

        config = parse_args()

        assert config.kbase_token == "token123"
        assert config.llm_provider == "openai"
        assert config.input_upa == "1/2/3"
        assert config.input_file_path is None
        assert config.narrative_name == "LLM Agent Annotation for test_object"

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'cborg', '-l', 'llm_key',
                        '-f', '/staging/forward.fq', '-f2', '/staging/reverse.fq',
                        '-t', 'pe_reads_noninterleaved'])
    @patch('scripts.full_pipeline.Workspace')
    def test_parse_args_with_paired_end_files(self, mock_ws):
        """Test parse_args with paired-end non-interleaved reads."""
        config = parse_args()

        assert config.input_file_path == "/staging/forward.fq"
        # Note: input_file_path2 is not stored in config, it's only used to build params
        assert config.input_file_path2 is None  # This field is not set by parse_args
        assert config.input_data_type == "pe_reads_noninterleaved"
        assert config.input_data_params["app_id"] == "kb_uploadmethods/import_fastq_noninterleaved_as_reads_from_staging"
        params = config.input_data_params["params"]
        assert params["fastq_fwd_staging_file_name"] == "/staging/forward.fq"
        assert params["fastq_rev_staging_file_name"] == "/staging/reverse.fq"

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'cborg', '-l', 'llm_key',
                        '-f', '/staging/interleaved.fq', '-t', 'pe_reads_interleaved'])
    @patch('scripts.full_pipeline.Workspace')
    def test_parse_args_with_interleaved_reads(self, mock_ws):
        """Test parse_args with paired-end interleaved reads."""
        config = parse_args()

        assert config.input_file_path == "/staging/interleaved.fq"
        assert config.input_data_type == "pe_reads_interleaved"
        assert config.input_data_params["app_id"] == "kb_uploadmethods/import_fastq_interleaved_as_reads_from_staging"

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'cborg', '-l', 'llm_key',
                        '-f', '/staging/test.fa', '-t', 'invalid_type'])
    def test_parse_args_invalid_data_type(self):
        """Test parse_args with invalid data type."""
        with pytest.raises(ValueError, match="must be one of"):
            parse_args()

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'cborg', '-l', 'llm_key',
                        '-u', '1/2/3', '-f2', '/staging/reverse.fq', '-t', 'pe_reads_noninterleaved'])
    @patch('scripts.full_pipeline.Workspace')
    def test_parse_args_f2_without_f(self, mock_ws):
        """Test parse_args with -f2 but no -f."""
        mock_ws_instance = mock_ws.return_value
        mock_obj_info = Mock()
        mock_obj_info.name = "test_object"
        mock_ws_instance.get_object_info.return_value = mock_obj_info

        # parse_args should succeed with -u but fail validation when -f2 is provided without -f
        with pytest.raises(ValueError, match="input_file_path must be provided first"):
            parse_args()

    @patch('sys.argv', ['script', '-k', 'token123', '-p', 'cborg', '-l', 'llm_key',
                        '-f', '/staging/test.fa', '-f2', '/staging/reverse.fq', '-t', 'assembly'])
    def test_parse_args_f2_with_wrong_type(self):
        """Test parse_args with -f2 but wrong data type."""
        with pytest.raises(ValueError, match="must only be provided with paired-end non-interleaved"):
            parse_args()


class TestDataTypeToParams:
    """Test data_type_to_params function."""

    def test_assembly_params(self):
        """Test parameters for assembly data type."""
        result = data_type_to_params(ASSEMBLY, "/path/to/file.fa", None, "test_file")

        assert result["app_id"] == "kb_uploadmethods/import_fasta_as_assembly_from_staging"
        assert result["params"]["staging_file_subdir_path"] == "/path/to/file.fa"
        assert result["params"]["assembly_name"] == "test_file_assembly"
        assert result["params"]["type"] == "mag"
        assert result["params"]["min_contig_length"] == 500

    def test_pe_reads_interleaved_params(self):
        """Test parameters for paired-end interleaved reads."""
        result = data_type_to_params(PE_READS_INT, "/path/to/reads.fq", None, "test_reads")

        assert result["app_id"] == "kb_uploadmethods/import_fastq_interleaved_as_reads_from_staging"
        assert result["params"]["fastq_fwd_staging_file_name"] == "/path/to/reads.fq"
        assert result["params"]["name"] == "test_reads_reads"
        assert result["params"]["sequencing_tech"] == "Unknown"
        assert result["params"]["single_genome"] == 1

    def test_pe_reads_noninterleaved_params(self):
        """Test parameters for paired-end non-interleaved reads."""
        result = data_type_to_params(PE_READS_NON_INT, "/path/to/fwd.fq", "/path/to/rev.fq", "test_reads")

        assert result["app_id"] == "kb_uploadmethods/import_fastq_noninterleaved_as_reads_from_staging"
        assert result["params"]["fastq_fwd_staging_file_name"] == "/path/to/fwd.fq"
        assert result["params"]["fastq_rev_staging_file_name"] == "/path/to/rev.fq"
        assert result["params"]["name"] == "test_reads_reads"

    def test_pe_reads_noninterleaved_no_second_file(self):
        """Test error when no second file for non-interleaved reads."""
        with pytest.raises(ValueError, match="second file path must be provided"):
            data_type_to_params(PE_READS_NON_INT, "/path/to/fwd.fq", None, "test_reads")

    def test_unsupported_data_type(self):
        """Test error for unsupported data type."""
        with pytest.raises(ValueError, match="Unsupported data type"):
            data_type_to_params("invalid_type", "/path/to/file", None, "test")


class TestImportData:
    """Test import_data and related functions."""

    @patch('scripts.full_pipeline.import_data_file')
    def test_import_data_with_file(self, mock_import):
        """Test import_data with file path."""
        mock_import.return_value = "123/45/6"
        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_file_path="/path/to/file",
            input_data_type="assembly",
            input_data_params={"app_id": "test_app", "params": {"key": "value"}},
            input_upa=None
        )

        result = import_data(1234, config)

        assert result == "123/45/6"
        mock_import.assert_called_once_with(1234, "test_app", {"key": "value"}, "token")

    @patch('scripts.full_pipeline.copy_data_object')
    def test_import_data_with_upa(self, mock_copy):
        """Test import_data with UPA."""
        mock_copy.return_value = "123/45/7"
        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="111/22/3"
        )

        result = import_data(1234, config)

        assert result == "123/45/7"
        mock_copy.assert_called_once_with(1234, "111/22/3", "token")

    def test_import_data_no_inputs(self):
        """Test import_data with neither file nor UPA."""
        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa=None
        )

        with pytest.raises(ValueError, match="requires either input_file_path or input_upa"):
            import_data(1234, config)

    def test_import_data_file_no_params(self):
        """Test import_data with file but no params."""
        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_file_path="/path/to/file",
            input_data_type="assembly",
            input_upa=None
        )

        with pytest.raises(ValueError, match="input_data_params must be present"):
            import_data(1234, config)


class TestCopyDataObject:
    """Test copy_data_object function."""

    @patch('scripts.full_pipeline.Workspace')
    def test_copy_data_object(self, mock_ws_class):
        """Test copying a data object."""
        mock_ws = mock_ws_class.return_value
        mock_result = Mock()
        mock_result.upa = "123/45/7"
        mock_ws.copy_object_to_workspace.return_value = mock_result

        result = copy_data_object(1234, "111/22/3", "token")

        assert result == "123/45/7"
        mock_ws_class.assert_called_once_with(token="token")
        mock_ws.copy_object_to_workspace.assert_called_once_with(1234, "111/22/3")


class TestImportDataFile:
    """Test import_data_file function."""

    @patch('scripts.full_pipeline.Workspace')
    @patch('scripts.full_pipeline.NarrativeMethodStore')
    @patch('scripts.full_pipeline.ExecutionEngine')
    @patch('scripts.full_pipeline.run_job')
    def test_import_data_file_success(self, mock_run_job, mock_ee_class, mock_nms_class, mock_ws_class):
        """Test successful data file import."""
        mock_result = Mock()
        mock_result.job_error = None
        mock_obj = Mock()
        mock_obj.object_upa = "123/45/6"
        mock_result.created_objects = [mock_obj]
        mock_run_job.return_value = mock_result

        result = import_data_file(1234, "test_app", {"key": "value"}, "token")

        assert result == "123/45/6"
        mock_ee_class.assert_called_once_with(token="token")
        mock_run_job.assert_called_once()

    @patch('scripts.full_pipeline.Workspace')
    @patch('scripts.full_pipeline.NarrativeMethodStore')
    @patch('scripts.full_pipeline.ExecutionEngine')
    @patch('scripts.full_pipeline.run_job')
    def test_import_data_file_with_error(self, mock_run_job, mock_ee_class, mock_nms_class, mock_ws_class):
        """Test data file import with job error."""
        mock_result = Mock()
        mock_result.job_error = "Import failed"
        mock_result.model_dump_json = Mock(return_value="{}")
        mock_run_job.return_value = mock_result

        with pytest.raises(RuntimeError, match="Import failed"):
            import_data_file(1234, "test_app", {"key": "value"}, "token")

    @patch('scripts.full_pipeline.Workspace')
    @patch('scripts.full_pipeline.NarrativeMethodStore')
    @patch('scripts.full_pipeline.ExecutionEngine')
    @patch('scripts.full_pipeline.run_job')
    def test_import_data_file_multiple_objects(self, mock_run_job, mock_ee_class, mock_nms_class, mock_ws_class):
        """Test data file import with unexpected multiple objects."""
        mock_result = Mock()
        mock_result.job_error = None
        mock_result.created_objects = [Mock(), Mock()]
        mock_result.model_dump_json = Mock(return_value="{}")
        mock_run_job.return_value = mock_result

        with pytest.raises(RuntimeError, match="Unexpected import results"):
            import_data_file(1234, "test_app", {"key": "value"}, "token")


class TestProcessMetadata:
    """Test process_metadata function."""

    @patch('scripts.full_pipeline.get_llm')
    @patch('scripts.full_pipeline.MetadataAgent')
    @patch('scripts.full_pipeline.Workspace')
    def test_process_metadata_cborg(self, mock_ws_class, mock_agent_class, mock_get_llm):
        """Test process_metadata with CBORG provider."""
        mock_ws = mock_ws_class.return_value
        mock_obj_info = Mock()
        mock_obj_info.metadata = {"key": "value"}
        mock_ws.get_object_info.return_value = mock_obj_info

        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_agent = mock_agent_class.return_value
        mock_agent.invoke.return_value = ({"output": "test response"}, 100)

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        result = process_metadata(1234, "123/45/6", config)

        assert result == {"output": "test response"}
        mock_get_llm.assert_called_once_with("gpt-5-cborg", api_key="llm_token")
        mock_agent_class.assert_called_once_with(llm=mock_llm, llm_name="gpt-5-cborg", token="token")

    @patch('scripts.full_pipeline.get_llm')
    @patch('scripts.full_pipeline.MetadataAgent')
    @patch('scripts.full_pipeline.Workspace')
    def test_process_metadata_openai(self, mock_ws_class, mock_agent_class, mock_get_llm):
        """Test process_metadata with OpenAI provider."""
        mock_ws = mock_ws_class.return_value
        mock_obj_info = Mock()
        mock_obj_info.metadata = {"key": "value"}
        mock_ws.get_object_info.return_value = mock_obj_info

        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_agent = mock_agent_class.return_value
        mock_agent.invoke.return_value = ({"output": "test response"}, 100)

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="openai",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        result = process_metadata(1234, "123/45/6", config)

        assert result == {"output": "test response"}
        mock_get_llm.assert_called_once_with("gpt-4o-openai", api_key="llm_token")


class TestRunAnalysisWorkflow:
    """Test run_analysis_workflow function."""

    @patch('scripts.full_pipeline.AnalysisWorkflow')
    def test_run_analysis_workflow_cborg(self, mock_workflow_class):
        """Test run_analysis_workflow with CBORG provider."""
        mock_workflow = mock_workflow_class.return_value
        mock_workflow.run.return_value = {"steps": ["step1", "step2"]}

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        result = run_analysis_workflow(1234, "123/45/6", "test context", config)

        assert result == {"steps": ["step1", "step2"]}
        mock_workflow_class.assert_called_once_with(
            analyst_llm="claude-sonnet-cborg-high",
            analyst_token="llm_token",
            app_flow_llm="claude-sonnet-cborg-high",
            app_flow_token="llm_token",
            kbase_token="token"
        )

    @patch('scripts.full_pipeline.AnalysisWorkflow')
    def test_run_analysis_workflow_openai(self, mock_workflow_class):
        """Test run_analysis_workflow with OpenAI provider."""
        mock_workflow = mock_workflow_class.return_value
        mock_workflow.run.return_value = {"steps": ["step1"]}

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="openai",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        result = run_analysis_workflow(1234, "123/45/6", "test context", config)

        assert result == {"steps": ["step1"]}
        mock_workflow_class.assert_called_once_with(
            analyst_llm="gpt-4o-openai",
            analyst_token="llm_token",
            app_flow_llm="gpt-4o-openai",
            app_flow_token="llm_token",
            kbase_token="token"
        )


class TestRunExecutionWorkflow:
    """Test run_execution_workflow function."""

    @patch('scripts.full_pipeline.ExecutionWorkflow')
    def test_run_execution_workflow_cborg(self, mock_workflow_class):
        """Test run_execution_workflow with CBORG provider."""
        mock_workflow = mock_workflow_class.return_value
        mock_state = Mock()
        mock_workflow.run.return_value = mock_state

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        analysis_state = Mock()
        result = run_execution_workflow(analysis_state, config)

        assert result == mock_state
        mock_workflow_class.assert_called_once_with(
            analyst_llm="gpt-4.1-cborg",
            analyst_token="llm_token",
            validator_llm="gpt-4.1-cborg",
            validator_token="llm_token",
            app_flow_llm="gpt-4.1-cborg",
            app_flow_token="llm_token",
            writer_llm="gpt-4.1-cborg",
            writer_token="llm_token",
            kbase_token="token"
        )
        mock_workflow.run.assert_called_once_with(analysis_state)

    @patch('scripts.full_pipeline.ExecutionWorkflow')
    def test_run_execution_workflow_openai(self, mock_workflow_class):
        """Test run_execution_workflow with OpenAI provider."""
        mock_workflow = mock_workflow_class.return_value
        mock_state = Mock()
        mock_workflow.run.return_value = mock_state

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="openai",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        analysis_state = Mock()
        result = run_execution_workflow(analysis_state, config)

        assert result == mock_state
        mock_workflow_class.assert_called_once_with(
            analyst_llm="gpt-4o-openai",
            analyst_token="llm_token",
            validator_llm="gpt-4o-openai",
            validator_token="llm_token",
            app_flow_llm="gpt-4o-openai",
            app_flow_token="llm_token",
            writer_llm="gpt-4o-openai",
            writer_token="llm_token",
            kbase_token="token"
        )


class TestWriteDraftMra:
    """Test write_draft_mra function."""

    @patch('scripts.full_pipeline.MraWriterGraph')
    @patch('scripts.full_pipeline.ExecutionEngine')
    @patch('scripts.full_pipeline.Workspace')
    def test_write_draft_mra_cborg(self, mock_ws_class, mock_ee_class, mock_writer_class):
        """Test write_draft_mra with CBORG provider."""
        mock_ws = mock_ws_class.return_value
        mock_ee = mock_ee_class.return_value
        mock_writer = mock_writer_class.return_value

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        write_draft_mra(1234, config)

        mock_ws_class.assert_called_once_with(token="token")
        mock_ee_class.assert_called_once_with(token="token")
        mock_writer_class.assert_called_once_with(
            mock_ws, mock_ee, "gpt-5-cborg", writer_token="llm_token"
        )
        mock_writer.run_workflow.assert_called_once_with(1234)

    @patch('scripts.full_pipeline.MraWriterGraph')
    @patch('scripts.full_pipeline.ExecutionEngine')
    @patch('scripts.full_pipeline.Workspace')
    def test_write_draft_mra_openai(self, mock_ws_class, mock_ee_class, mock_writer_class):
        """Test write_draft_mra with OpenAI provider."""
        mock_ws = mock_ws_class.return_value
        mock_ee = mock_ee_class.return_value
        mock_writer = mock_writer_class.return_value

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="openai",
            llm_token="llm_token",
            narrative_name="Test",
            input_data_type="assembly",
            input_upa="1/2/3"
        )

        write_draft_mra(1234, config)

        mock_writer_class.assert_called_once_with(
            mock_ws, mock_ee, "gpt-o1-openai", writer_token="llm_token"
        )


class TestRunPipeline:
    """Test run_pipeline function."""

    @patch('scripts.full_pipeline.write_draft_mra')
    @patch('scripts.full_pipeline.run_execution_workflow')
    @patch('scripts.full_pipeline.run_analysis_workflow')
    @patch('scripts.full_pipeline.process_metadata')
    @patch('scripts.full_pipeline.import_data')
    @patch('scripts.full_pipeline.NarrativeService')
    def test_run_pipeline_complete(self, mock_ns_class, mock_import, mock_process_meta,
                                   mock_analysis, mock_execution, mock_write):
        """Test complete pipeline run."""
        # Setup mocks
        mock_ns = mock_ns_class.return_value
        mock_ns.create_new_narrative.return_value = 1234

        mock_import.return_value = "123/45/6"
        mock_process_meta.return_value = {"output": "metadata context"}
        mock_analysis.return_value = {"steps": ["step1"]}
        mock_execution.return_value = Mock()

        config = PipelineConfig(
            kbase_token="token",
            llm_provider="cborg",
            llm_token="llm_token",
            narrative_name="Test Narrative",
            input_file_path="/path/to/file.fa",
            input_data_type="assembly",
            input_data_params={"app_id": "test_app", "params": {}},
            input_upa=None
        )

        run_pipeline(config)

        # Verify calls
        mock_ns_class.assert_called_once_with(token="token")
        mock_ns.create_new_narrative.assert_called_once_with("Test Narrative")
        mock_import.assert_called_once_with(1234, config)
        mock_process_meta.assert_called_once_with(1234, "123/45/6", config)
        mock_analysis.assert_called_once_with(1234, "123/45/6", "metadata context", config)
        mock_execution.assert_called_once()
        mock_write.assert_called_once_with(1234, config)


class TestConstants:
    """Test module constants."""

    def test_data_types_constant(self):
        """Test DATA_TYPES constant contains all expected types."""
        assert ASSEMBLY in DATA_TYPES
        assert PE_READS_INT in DATA_TYPES
        assert PE_READS_NON_INT in DATA_TYPES
        assert SE_READS in DATA_TYPES
        assert len(DATA_TYPES) == 4

    def test_data_type_values(self):
        """Test data type constant values."""
        assert ASSEMBLY == "assembly"
        assert PE_READS_INT == "pe_reads_interleaved"
        assert PE_READS_NON_INT == "pe_reads_noninterleaved"
        assert SE_READS == "se_reads"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_data_type_to_params_case_insensitive(self):
        """Test that data type comparison should be case-insensitive in parse_args."""
        # This is handled in parse_args with .lower()
        with patch('sys.argv', ['script', '-k', 'token', '-p', 'cborg', '-l', 'llm_key',
                                '-f', '/test.fa', '-t', 'ASSEMBLY']):
            with patch('scripts.full_pipeline.Workspace'):
                config = parse_args()
                assert config.input_data_type == "assembly"

    @patch('scripts.full_pipeline.Workspace')
    @patch('scripts.full_pipeline.NarrativeMethodStore')
    @patch('scripts.full_pipeline.ExecutionEngine')
    @patch('scripts.full_pipeline.run_job')
    def test_import_data_file_empty_created_objects(self, mock_run_job, mock_ee, mock_nms, mock_ws):
        """Test import_data_file with empty created_objects list."""
        mock_result = Mock()
        mock_result.job_error = None
        mock_result.created_objects = []
        mock_result.model_dump_json = Mock(return_value="{}")
        mock_run_job.return_value = mock_result

        # This should raise an error because we expect at least one object
        with pytest.raises(IndexError):
            import_data_file(1234, "test_app", {}, "token")
