package local.skills.review;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.gumtreediff.actions.model.Action;
import com.github.gumtreediff.actions.model.Update;
import com.github.gumtreediff.tree.Tree;
import gr.uom.java.xmi.diff.CodeRange;
import org.refactoringminer.api.Refactoring;
import org.refactoringminer.astDiff.models.ASTDiff;
import org.refactoringminer.astDiff.models.ProjectASTDiff;
import org.refactoringminer.rm1.GitHistoryRefactoringMinerImpl;

import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Read-only AST evidence adapter. The Python caller supplies bounded snapshots. */
public final class ReviewEngine {
    private static final int MAX_REFACTORINGS = 1000;
    private static final int MAX_ACTIONS = 2000;

    public static void main(String[] args) throws Exception {
        PrintStream protocol = System.out;
        // Some upstream dependencies print messages directly. Keep stdout valid JSON.
        System.setOut(System.err);
        ObjectMapper json = new ObjectMapper();
        try {
            if (args.length != 3 || !"directories".equals(args[0])) {
                throw new IllegalArgumentException("Usage: directories BEFORE AFTER");
            }
            Path before = Path.of(args[1]).toAbsolutePath().normalize();
            Path after = Path.of(args[2]).toAbsolutePath().normalize();
            if (!Files.isDirectory(before) || !Files.isDirectory(after)) {
                throw new IllegalArgumentException("Both snapshot directories must exist");
            }
            long started = System.nanoTime();
            ProjectASTDiff project = new GitHistoryRefactoringMinerImpl()
                    .diffAtDirectories(before, after);
            if (project == null) {
                throw new IllegalStateException("RefactoringMiner could not produce an AST diff; inspect stderr");
            }
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("engine", "RefactoringMiner");
            result.put("version", "3.0.11");
            result.put("adapter_version", "1.2.0");
            result.put("edit_distance", "exact-utf16-affix-trimmed");
            result.put("core_overrides", List.of("StringDistance", "ReplacementUtil.keepReservedTokens"));
            List<Map<String, Object>> refactorings = new ArrayList<>();
            List<Refactoring> detected = project.getRefactorings();
            if (detected == null) detected = List.of();
            for (Refactoring item : detected) {
                if (refactorings.size() == MAX_REFACTORINGS) break;
                Map<String, Object> entry = new LinkedHashMap<>();
                entry.put("type", item.getName());
                entry.put("description", item.toString());
                entry.put("before", locations(item.leftSide()));
                entry.put("after", locations(item.rightSide()));
                refactorings.add(entry);
            }
            result.put("refactoring_count", detected.size());
            result.put("refactorings", refactorings);
            result.put("ast_diff_count", project.getDiffSet().size());
            result.put("move_ast_diff_count", project.getMoveDiffSet().size());
            List<Map<String, Object>> diffs = new ArrayList<>();
            int[] emitted = {0};
            int[] total = {0};
            Map<String, LineIndex> lines = new HashMap<>();
            for (ASTDiff diff : project.getDiffSet()) {
                diffs.add(diffSummary(diff, project, false, emitted, total, lines));
            }
            for (ASTDiff diff : project.getMoveDiffSet()) {
                diffs.add(diffSummary(diff, project, true, emitted, total, lines));
            }
            result.put("ast_diffs", diffs);
            result.put("ast_action_count", total[0]);
            result.put("truncated", detected.size() > MAX_REFACTORINGS || total[0] > MAX_ACTIONS);
            result.put("elapsed_ms", (System.nanoTime() - started) / 1_000_000);
            protocol.println(json.writeValueAsString(result));
        } catch (Exception | LinkageError failure) {
            Map<String, Object> error = new LinkedHashMap<>();
            error.put("engine", "RefactoringMiner");
            error.put("version", "3.0.11");
            error.put("error", failure.getClass().getSimpleName() + ": " + failure.getMessage());
            failure.printStackTrace(System.err);
            protocol.println(json.writeValueAsString(error));
            System.exit(2);
        }
    }

    private static List<Map<String, Object>> locations(List<CodeRange> ranges) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (CodeRange range : ranges) {
            Map<String, Object> location = new LinkedHashMap<>();
            location.put("file_path", range.getFilePath());
            location.put("start_line", range.getStartLine());
            location.put("end_line", range.getEndLine());
            location.put("start_column", range.getStartColumn());
            location.put("end_column", range.getEndColumn());
            location.put("description", range.getDescription());
            location.put("code_element", range.getCodeElement());
            result.add(location);
        }
        return result;
    }

    private static Map<String, Object> diffSummary(ASTDiff diff, ProjectASTDiff project,
                                                  boolean crossFileMove, int[] emitted, int[] total,
                                                  Map<String, LineIndex> lines) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("before_path", diff.getSrcPath());
        result.put("after_path", diff.getDstPath());
        result.put("cross_file_move_view", crossFileMove);
        List<Map<String, Object>> actions = new ArrayList<>();
        for (Action action : diff.editScript) {
            total[0]++;
            if (emitted[0] >= MAX_ACTIONS) continue;
            emitted[0]++;
            Tree node = action.getNode();
            boolean inserted = action.getName().startsWith("insert");
            String path = inserted ? diff.getDstPath() : diff.getSrcPath();
            String text = (inserted ? project.getFileContentsAfter() : project.getFileContentsBefore())
                    .getOrDefault(path, "");
            LineIndex index = lines.computeIfAbsent((inserted ? "after:" : "before:") + path,
                    key -> new LineIndex(text));
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("action", action.getName());
            entry.put("node_type", node.getType().name);
            entry.put("side", inserted ? "after" : "before");
            entry.put("file_path", path);
            entry.put("start_offset", node.getPos());
            entry.put("end_offset", node.getEndPos());
            entry.put("start_line", index.lineAt(node.getPos()));
            entry.put("end_line", index.lineAt(Math.max(node.getPos(), node.getEndPos() - 1)));
            entry.put("label", clipped(node.getLabel()));
            if (action instanceof Update update) entry.put("new_label", clipped(update.getValue()));
            actions.add(entry);
        }
        result.put("actions", actions);
        return result;
    }

    private static String clipped(String value) {
        return value == null || value.length() <= 400 ? value : value.substring(0, 400) + "…";
    }

    private static final class LineIndex {
        private final int length;
        private final int[] newlines;

        LineIndex(String content) {
            length = content.length();
            int count = 0;
            for (int i = 0; i < length; i++) if (content.charAt(i) == '\n') count++;
            newlines = new int[count];
            for (int i = 0, j = 0; i < length; i++) if (content.charAt(i) == '\n') newlines[j++] = i;
        }

        Integer lineAt(int offset) {
            if (offset < 0 || offset > length) return null;
            int position = Arrays.binarySearch(newlines, offset);
            return 1 + (position >= 0 ? position : -position - 1);
        }
    }
}
