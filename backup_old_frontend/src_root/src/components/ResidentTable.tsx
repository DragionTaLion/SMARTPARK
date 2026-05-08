/**
 * ResidentTable — CRUD bảng cư dân
 * Dữ liệu thật từ /api/residents qua SmartParkContext
 * Giữ phong cách Velorah glassmorphism
 */

import { motion, AnimatePresence } from 'motion/react';
import { useState } from 'react';
import { useSmartPark } from '../context/SmartParkContext';
import { Users, Plus, Trash2, Loader2, X, Check } from 'lucide-react';

export default function ResidentTable() {
  const { residents, addResident, deleteResident, isLoading } = useSmartPark();

  // Form state
  const [showForm, setShowForm]         = useState(false);
  const [formData, setFormData]         = useState({ bien_so_xe: '', ten_chu_xe: '', so_can_ho: '' });
  const [submitting, setSubmitting]     = useState(false);
  const [deletingId, setDeletingId]     = useState<number | null>(null);
  const [formError, setFormError]       = useState('');
  const [formSuccess, setFormSuccess]   = useState('');

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.bien_so_xe.trim() || !formData.ten_chu_xe.trim()) {
      setFormError('Điền đầy đủ biển số và tên chủ xe');
      return;
    }
    setSubmitting(true);
    setFormError('');
    try {
      await addResident(formData);
      setFormSuccess(`Đã thêm: ${formData.ten_chu_xe}`);
      setFormData({ bien_so_xe: '', ten_chu_xe: '', so_can_ho: '' });
      setTimeout(() => { setFormSuccess(''); setShowForm(false); }, 2000);
    } catch (e: any) {
      setFormError(e.message || 'Lỗi thêm cư dân');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Xóa cư dân "${name}"?`)) return;
    setDeletingId(id);
    try {
      await deleteResident(id);
    } catch (e: any) {
      alert(e.message || 'Lỗi xóa cư dân');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <h2 className="font-serif text-lg flex items-center gap-2">
          <Users className="w-4 h-4 text-electric" />
          Cư dân ({residents.length})
        </h2>
        <button
          onClick={() => { setShowForm(v => !v); setFormError(''); setFormSuccess(''); }}
          className="p-1.5 rounded-lg bg-electric/10 hover:bg-electric/20 border border-electric/30 text-electric transition-colors"
        >
          {showForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
        </button>
      </div>

      {/* Add Form */}
      <AnimatePresence>
        {showForm && (
          <motion.form
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            onSubmit={handleAdd}
            className="overflow-hidden border-b border-white/10"
          >
            <div className="p-3 space-y-2">
              <input
                type="text"
                placeholder="Biển số (VD: 43A-12345)"
                value={formData.bien_so_xe}
                onChange={e => setFormData(p => ({ ...p, bien_so_xe: e.target.value.toUpperCase() }))}
                className="w-full bg-black/20 border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 transition-colors"
              />
              <input
                type="text"
                placeholder="Tên chủ xe"
                value={formData.ten_chu_xe}
                onChange={e => setFormData(p => ({ ...p, ten_chu_xe: e.target.value }))}
                className="w-full bg-black/20 border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 transition-colors"
              />
              <input
                type="text"
                placeholder="Số căn hộ"
                value={formData.so_can_ho}
                onChange={e => setFormData(p => ({ ...p, so_can_ho: e.target.value }))}
                className="w-full bg-black/20 border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white placeholder:text-white/20 focus:outline-none focus:border-electric/50 transition-colors"
              />

              {formError   && <p className="text-red-400 text-[10px] font-mono">{formError}</p>}
              {formSuccess && (
                <p className="text-green-400 text-[10px] font-mono flex items-center gap-1">
                  <Check className="w-3 h-3" /> {formSuccess}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-1.5 bg-electric text-midnight text-xs font-mono rounded hover:bg-electric/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
              >
                {submitting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                {submitting ? 'Đang lưu...' : 'Thêm cư dân'}
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Table */}
      <div className="flex-1 overflow-y-auto scrollbar-hide">
        {isLoading ? (
          <div className="flex items-center justify-center h-20">
            <Loader2 className="w-5 h-5 animate-spin text-electric/50" />
          </div>
        ) : residents.length === 0 ? (
          <div className="flex items-center justify-center h-20 text-white/20 text-xs font-mono">
            Chưa có cư dân nào
          </div>
        ) : (
          <AnimatePresence>
            {residents.map((r, i) => (
              <motion.div
                key={r.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ delay: i * 0.02, duration: 0.3 }}
                className="flex items-center gap-2 px-3 py-2 border-b border-white/5 hover:bg-white/3 group transition-colors"
              >
                {/* Avatar */}
                <div className="w-7 h-7 rounded-full bg-electric/10 border border-electric/20 flex items-center justify-center flex-shrink-0">
                  <span className="text-[9px] font-mono text-electric">
                    {r.ten_chu_xe.charAt(0).toUpperCase()}
                  </span>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="text-white text-[11px] font-medium truncate">{r.ten_chu_xe}</div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-electric text-[9px] font-mono">{r.bien_so_xe}</span>
                    {r.so_can_ho && (
                      <span className="text-white/30 text-[9px] font-mono">P.{r.so_can_ho}</span>
                    )}
                  </div>
                </div>

                {/* Delete button */}
                <button
                  onClick={() => handleDelete(r.id, r.ten_chu_xe)}
                  disabled={deletingId === r.id}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-all"
                >
                  {deletingId === r.id
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : <Trash2 className="w-3 h-3" />}
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
