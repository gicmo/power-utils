// Small tool to record current total energy (of all batteries)
//  currently writes data to /var/cache/pt/drain.csv
//  meant to be run by systemd-suspend (man systemd-suspend.service)
//  and therefore should be put into /usr/lib/systemd/system-sleep/
#include <glib.h>
#include <glib/gprintf.h>

#include <gio/gio.h>
#include <time.h>
#include <math.h>
#include <string.h>

#define PT_TYPE_BATTERY pt_battery_get_type ()
G_DECLARE_FINAL_TYPE(PtBattery, pt_battery, PT, BATTERY, GObject)
PtBattery *    pt_battery_new    (GFile *path);

typedef enum _BatteryUnit {

  UNIT_INVALID = 0,
  UNIT_ENERGY,
  UNIT_CHARGE

} BatteryUnit;

struct _PtBattery {
  GObject     parent;
  GFile      *path;

  BatteryUnit unit;
  guint64     energy_now;
  guint64     voltage_now;
  guint64     charge_now;

  float       capacity;

  gint64      timestamp;
};

G_DEFINE_TYPE (PtBattery, pt_battery, G_TYPE_OBJECT);

static void pt_battery_finalize(PtBattery *bat) {
  g_object_unref(bat->path);
}

static void pt_battery_class_init (PtBatteryClass *klass) {
  G_OBJECT_CLASS(klass)->finalize = (GObjectFinalizeFunc) pt_battery_finalize;
}

static void pt_battery_init (PtBattery *bat) { }

static gboolean file_read_uint64 (GFile *base,
                                  const char *name,
                                  guint64 *out,
                                  GError **error) {
  char *data = NULL, *endptr;
  gint64 res;
  g_autoptr(GFile) fp = g_file_get_child(base, name);

  if (!g_file_load_contents(fp, NULL, &data, NULL, NULL, error)) {
    return FALSE;
  }

  res = g_ascii_strtoull(data, &endptr, 10);
  if (endptr == data) {
    return FALSE;
  }

  *out = res;
  return TRUE;
}

static gboolean file_read_float (GFile *base,
                                 const char *name,
                                 float *out,
                                 GError **error) {
  char *data = NULL, *endptr;
  double res;
  g_autoptr(GFile) fp = g_file_get_child(base, name);

  if (!g_file_load_contents(fp, NULL, &data, NULL, NULL, error)) {
    return FALSE;
  }

  res = g_ascii_strtod(data, &endptr);
  if (endptr == data) {
    return FALSE;
  }

  *out = (float) res;
  return TRUE;
}

static gboolean pt_battery_refresh_data (PtBattery *bat, GError **error) {
  guint64 energy_now;
  gboolean ok;
  time_t now;
  float capacity;
  BatteryUnit unit = UNIT_ENERGY;

  ok = file_read_uint64(bat->path, "energy_now", &energy_now, error);

  if (!ok) {
    guint64 charge_now = 0;
    guint64 voltage_now = 0;
    ok = file_read_uint64(bat->path, "charge_now", &charge_now, error);

    if (ok) {
      ok = file_read_uint64(bat->path, "voltage_now", &voltage_now, error);
    }

    unit = UNIT_CHARGE;
    energy_now = charge_now * voltage_now / (1000*1000);
  }

  time(&now);

  if (!ok || now == (time_t)-1) {
    bat->unit = UNIT_INVALID;
    return FALSE;
  }

  ok = file_read_float(bat->path, "capacity", &capacity, NULL);
  if (!ok) {
    capacity = -1;
  }

  bat->timestamp = (gint64) now;
  bat->energy_now = energy_now;
  bat->unit = unit;
  bat->capacity = capacity;
  return ok;
}

PtBattery *
pt_battery_new (GFile *path) {
  PtBattery *bat = (PtBattery *) g_object_new(PT_TYPE_BATTERY, NULL);
  bat->path = (GFile *) g_object_ref(path);
  return bat;
}

static gboolean device_is_battery(const char *name) {
  return g_str_has_prefix (name, "BAT");
}

static gboolean device_is_ac(const char *name) {
  return g_str_has_prefix (name, "AC") ||
    g_str_has_prefix (name, "ADP");
}

static GPtrArray *
list_devices (GError **error) {
  GPtrArray *devices = NULL;
  g_autoptr(GFile) sys_ps = NULL;
  g_autoptr(GFileEnumerator) iter = NULL;

  sys_ps = g_file_new_for_path("/sys/class/power_supply");

  iter = g_file_enumerate_children(sys_ps,
                                   "standard::name,standard::type",
                                   G_FILE_QUERY_INFO_NONE,
                                   NULL, error);

  if (!iter) {
    return NULL;
  }

  devices = g_ptr_array_new_with_free_func((GDestroyNotify) g_object_unref);
  while (TRUE) {
    GFileInfo *info;
    GFile *f;

    if (!g_file_enumerator_iterate (iter, &info, &f, NULL, error))
      continue;

    if (!info)
      break;

    const char *name = g_file_info_get_name (info);
    if (!device_is_battery(name) && !device_is_ac(name)) {
      continue;
    }

    g_ptr_array_add(devices, g_object_ref(f));
  }

  return devices;
}

static GPtrArray *
find_batteries (GPtrArray *devices) {
  GPtrArray *bats;
  int i;

  bats = g_ptr_array_new_with_free_func((GDestroyNotify) g_object_unref);
  for (i = 0; i < devices->len; i++) {
    PtBattery *bat;
    GFile *d;

    d = (GFile *) g_ptr_array_index (devices, i);
    const char *name = g_file_get_basename(d);

    if (!device_is_battery(name)) {
      continue;
    }

    bat = pt_battery_new(d);
    g_ptr_array_add(bats, bat);
  }

  return bats;
}

gboolean
ac_is_online (GPtrArray *devices, gboolean *status, GError **error) {
  int i;
  guint64 data;
  gboolean ok;
  g_autoptr(GFile) ac = NULL;

  //This logic assumes we have only one, which seems reasonable
  //for most notebooks but of course might be wrong
  for (i = 0; i < devices->len; i++) {
    GFile *d = (GFile *) g_ptr_array_index (devices, i);
    const char *name = g_file_get_basename(d);

    if (device_is_ac(name)) {
      ac = (GFile *) g_object_ref(d);
      break;
    }
  }

  if (ac == NULL) {
    return FALSE;
  }

  ok = file_read_uint64(ac, "online", &data, error);
  if (!ok) {
    return FALSE;
  }

  *status = data != 0;
  return TRUE;
}

static gboolean
total_energy_now (GPtrArray *bats,
                  guint64 *energy,
                  gint64 *timestamp,
                  GError **error) {
  int i;
  guint64 total = 0;
  gint64 ts = 0;

  for (i = 0; i < bats->len; i++) {
    PtBattery *b = (PtBattery *) g_ptr_array_index (bats, i);
    if (!pt_battery_refresh_data(b, error)) {
      return FALSE;
    }

     total += b->energy_now;
     if (b->timestamp > ts) {
       ts = b->timestamp;
     }
  }

  *energy = total;
  *timestamp = ts;
  return TRUE;
}

// Assume data has been refreshed
static gboolean
total_capacity_now (GPtrArray *bats,
                    float *capacity,
                    GError **error)
{
  int i;
  int count = 0;
  double total = 0.0;

  for (i = 0; i < bats->len; i++) {
    PtBattery *b = (PtBattery *) g_ptr_array_index (bats, i);

    if (b->capacity > -1.0f) {
      total += b->capacity;
      count++;
    }
  }

  *capacity = total / count;
  return count > 0;
}

static GFileOutputStream *
open_data_file(GError **error) {
  gboolean ok;
  g_autoptr(GFile) df = NULL;
  g_autoptr(GFile) dir = g_file_new_for_path("/var/cache/pt");
  g_autoptr(GFileInfo) info = NULL;
  GFileOutputStream *out;

  if (!g_file_query_exists(dir, NULL)) {
    ok = g_file_make_directory(dir, NULL, error);
    if (!ok) {
      //check for EEXIST error
      return NULL;
    }
  }

  df = g_file_get_child(dir, "drain.csv");
  out = g_file_append_to(df, G_FILE_CREATE_NONE, NULL, error);

  if (out  == NULL) {
    return NULL;
  }

  info = g_file_output_stream_query_info(out, "standard::size", NULL, error);
  if (info == NULL) {
    g_object_unref(out);
    return NULL;
  }

  if (g_file_info_get_size(info) == 0) {
    static const char *data = "action,timestamp,ac,energy_total,capacity_total\n";
    ok = g_output_stream_write_all(G_OUTPUT_STREAM(out),
                                   data, strlen(data), NULL, NULL, error);
    if (!ok) {
      g_object_unref(out);
      g_file_delete(df, NULL, NULL);
      return FALSE;
    }
  }

  return out;
}

#if 0
static void
dump_batteries(GPtrArray *bats) {
  int i;
    for (i = 0; i < bats->len; i++) {
    PtBattery *b = (PtBattery *) g_ptr_array_index (bats, i);
    const char *name = g_file_get_basename(b->path);
    g_fprintf(stderr, "%s\n", name);
    if (pt_battery_refresh_data(b)) {
      g_fprintf(stderr, "\t energy_now: %lu [%ld]\n", b->energy_now, b->timestamp);
    }
  }
}
#endif

int main (int argc, char **argv) {
  g_autoptr(GPtrArray) devices = NULL;
  g_autoptr(GPtrArray) bats = NULL;
  gboolean acon, ok;
  guint64 energy;
  float capacity = -1.0f;
  gint64 timestamp;
  const char *action;
  g_autoptr(GFileOutputStream) out = NULL;
  GError *error = NULL;

  devices = list_devices(&error);

  if (devices == NULL) {
    g_fprintf(stderr, "Error obtaining power device: %s\n", error->message);
    return -1;
  }

  bats = find_batteries(devices);

  if (bats->len < 1) {
    g_fprintf(stderr, "No batteries found!\n");
    return -1;
  }

#if 0
  dump_batteries(bats);
#endif

  ok = ac_is_online(devices, &acon, &error);
  if (!ok) {
    g_fprintf(stderr, "Could not find AC device: %s\n", error->message);
    return -1;
  }

  ok = total_energy_now(bats, &energy, &timestamp, &error);
  if (!ok) {
    g_fprintf(stderr, "Could not get total energy: %s\n", error->message);
    return -1;
  }
  //ignore errors for capacity
  // will result in it being -1.0f
  total_capacity_now(bats, &capacity, NULL);

  out = open_data_file(&error);
  if (!out) {
    g_fprintf(stderr, "Could not open data file: %s\n", error->message);
    return -1;
  }

  action = "check";
  if (argc > 1) {
    action = argv[1];
  }

  ok = g_output_stream_printf(G_OUTPUT_STREAM(out), NULL, NULL, NULL,
                              "%s,%ld,%d,%lu,%.2f\n",
                              action, timestamp, acon ? 1 : 0,
                              energy, capacity);
  if (!ok) {
    return -1;
  }

  ok = g_output_stream_close(G_OUTPUT_STREAM(out), NULL, &error);

  if (!ok) {
    g_fprintf(stderr, "Could not close data file: %s\n", error->message);
    return -1;
  }

  return 0;
}
