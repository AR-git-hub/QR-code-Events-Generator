package ru.qrticket.validator;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public class MainActivity extends Activity {
    private static final int REQUEST_IMPORT = 1001;
    private static final int REQUEST_CAMERA = 1002;
    private static final String PREFS = "validator_state";
    private static final String KEY_TICKETS = "tickets_json";
    private static final String KEY_USED = "used_json";
    private static final String KEY_LOG = "scan_log_json";

    private final Map<String, Ticket> tickets = new HashMap<>();
    private final Set<String> usedCodes = new HashSet<>();
    private final JSONArray scanLog = new JSONArray();

    private TextView statusView;
    private TextView statsView;
    private TextView lastScanView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        loadState();
        renderStats();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 36, 32, 32);

        TextView title = new TextView(this);
        title.setText("QR Ticket Validator");
        title.setTextSize(24);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title);

        statusView = new TextView(this);
        statusView.setText("Импортируйте JSON-базу билетов.");
        statusView.setTextSize(16);
        statusView.setPadding(0, 24, 0, 12);
        root.addView(statusView);

        statsView = new TextView(this);
        statsView.setTextSize(16);
        statsView.setPadding(0, 0, 0, 24);
        root.addView(statsView);

        Button importButton = new Button(this);
        importButton.setText("Импорт базы JSON");
        importButton.setOnClickListener(v -> openImportPicker());
        root.addView(importButton);

        Button scanButton = new Button(this);
        scanButton.setText("Сканировать QR");
        scanButton.setOnClickListener(v -> startScan());
        root.addView(scanButton);

        Button resetButton = new Button(this);
        resetButton.setText("Сбросить отметки прохода");
        resetButton.setOnClickListener(v -> resetUsedMarks());
        root.addView(resetButton);

        lastScanView = new TextView(this);
        lastScanView.setTextSize(18);
        lastScanView.setPadding(0, 28, 0, 0);

        ScrollView scrollView = new ScrollView(this);
        scrollView.addView(lastScanView);
        root.addView(scrollView, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1
        ));

        setContentView(root);
    }

    private void openImportPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/json", "text/plain", "application/octet-stream"});
        startActivityForResult(intent, REQUEST_IMPORT);
    }

    private void startScan() {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQUEST_CAMERA);
            return;
        }

        IntentIntegrator integrator = new IntentIntegrator(this);
        integrator.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE);
        integrator.setPrompt("Наведите камеру на QR билета");
        integrator.setBeepEnabled(true);
        integrator.setOrientationLocked(true);
        integrator.initiateScan();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_IMPORT && resultCode == RESULT_OK && data != null) {
            importTickets(data.getData());
            return;
        }

        IntentResult result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (result != null && result.getContents() != null) {
            validateCode(result.getContents());
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_CAMERA) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startScan();
            } else {
                lastScanView.setText("Нет доступа к камере. Разрешите камеру в настройках приложения.");
                Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                intent.setData(Uri.parse("package:" + getPackageName()));
                startActivity(intent);
            }
        }
    }

    private void importTickets(Uri uri) {
        try {
            String json = readText(uri);
            JSONObject root = new JSONObject(json);
            JSONArray array = root.getJSONArray("tickets");

            tickets.clear();
            usedCodes.clear();
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.getJSONObject(i);
                Ticket ticket = Ticket.fromJson(item);
                tickets.put(ticket.code, ticket);
            }

            saveTicketsJson(array);
            saveUsedJson();
            statusView.setText("База импортирована. Можно сканировать.");
            lastScanView.setText("Импортировано билетов: " + tickets.size());
            renderStats();
        } catch (Exception exc) {
            lastScanView.setText("Ошибка импорта: " + exc.getMessage());
        }
    }

    private String readText(Uri uri) throws Exception {
        InputStream stream = getContentResolver().openInputStream(uri);
        if (stream == null) {
            throw new IllegalArgumentException("Файл не найден");
        }
        BufferedReader reader = new BufferedReader(
            new InputStreamReader(stream, StandardCharsets.UTF_8)
        );
        StringBuilder builder = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            builder.append(line).append('\n');
        }
        reader.close();
        return builder.toString();
    }

    private void validateCode(String code) {
        Ticket ticket = tickets.get(code);
        if (ticket == null) {
            showResult("НЕ НАЙДЕН", "Такого QR нет в импортированной базе.", "#991b1b");
            appendLog(code, "not_found");
            return;
        }

        if (usedCodes.contains(code)) {
            showResult(
                "УЖЕ ИСПОЛЬЗОВАН",
                ticket.description() + "\nПовторный проход запрещен.",
                "#92400e"
            );
            appendLog(code, "duplicate");
            return;
        }

        usedCodes.add(code);
        saveUsedJson();
        showResult("ПРОПУСТИТЬ", ticket.description(), "#166534");
        appendLog(code, "accepted");
        renderStats();
    }

    private void showResult(String title, String details, String color) {
        lastScanView.setText(title + "\n\n" + details);
        try {
            lastScanView.setTextColor(android.graphics.Color.parseColor(color));
        } catch (Exception ignored) {
            lastScanView.setTextColor(android.graphics.Color.BLACK);
        }
    }

    private void resetUsedMarks() {
        usedCodes.clear();
        saveUsedJson();
        renderStats();
        lastScanView.setTextColor(android.graphics.Color.BLACK);
        lastScanView.setText("Отметки прохода сброшены. База билетов осталась на телефоне.");
    }

    private void renderStats() {
        statsView.setText(
            "Билетов в базе: " + tickets.size() + "\n" +
            "Уже прошли: " + usedCodes.size() + "\n" +
            "Осталось: " + Math.max(0, tickets.size() - usedCodes.size())
        );
    }

    private void loadState() {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        try {
            JSONArray array = new JSONArray(prefs.getString(KEY_TICKETS, "[]"));
            tickets.clear();
            for (int i = 0; i < array.length(); i++) {
                Ticket ticket = Ticket.fromJson(array.getJSONObject(i));
                tickets.put(ticket.code, ticket);
            }

            JSONArray used = new JSONArray(prefs.getString(KEY_USED, "[]"));
            usedCodes.clear();
            for (int i = 0; i < used.length(); i++) {
                usedCodes.add(used.getString(i));
            }
        } catch (JSONException ignored) {
            tickets.clear();
            usedCodes.clear();
        }
    }

    private void saveTicketsJson(JSONArray array) {
        getSharedPreferences(PREFS, MODE_PRIVATE)
            .edit()
            .putString(KEY_TICKETS, array.toString())
            .apply();
    }

    private void saveUsedJson() {
        JSONArray array = new JSONArray();
        for (String code : usedCodes) {
            array.put(code);
        }
        getSharedPreferences(PREFS, MODE_PRIVATE)
            .edit()
            .putString(KEY_USED, array.toString())
            .apply();
    }

    private void appendLog(String code, String result) {
        JSONObject item = new JSONObject();
        try {
            item.put("code", code);
            item.put("result", result);
            item.put("time", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date()));
            scanLog.put(item);
            getSharedPreferences(PREFS, MODE_PRIVATE)
                .edit()
                .putString(KEY_LOG, scanLog.toString())
                .apply();
        } catch (JSONException ignored) {
        }
    }

    private static class Ticket {
        final String code;
        final String ticketId;
        final String type;
        final String tariff;
        final int amountKopecks;
        final String createdAt;

        Ticket(String code, String ticketId, String type, String tariff, int amountKopecks, String createdAt) {
            this.code = code;
            this.ticketId = ticketId;
            this.type = type;
            this.tariff = tariff;
            this.amountKopecks = amountKopecks;
            this.createdAt = createdAt;
        }

        static Ticket fromJson(JSONObject object) throws JSONException {
            return new Ticket(
                object.getString("code"),
                object.optString("ticket_id", ""),
                object.optString("type", "paid"),
                object.optString("tariff", ""),
                object.optInt("amount_kopecks", 0),
                object.optString("created_at", "")
            );
        }

        String description() {
            return "Тип: " + type + "\n" +
                "Тариф: " + tariff + "\n" +
                "Билет: " + ticketId + "\n" +
                "Сумма: " + (amountKopecks / 100) + " руб.\n" +
                "Создан: " + createdAt;
        }
    }
}
